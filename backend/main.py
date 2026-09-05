import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import database
import market_data
import change_detection
import portfolio_insights
import news
from symbols import search_symbols, SYMBOL_INDEX

NIFTY_INDEX_SYMBOL = "^NSEI"

app = FastAPI(title="Smart Watchlist API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    database.init_db()


class AddSymbolBody(BaseModel):
    device_id: str
    symbol: str


@app.post("/device/register")
def register_device():
    return {"device_id": str(uuid.uuid4())}


@app.get("/stocks/search")
def search(q: str = ""):
    matches = search_symbols(q)
    enriched = []
    for m in matches:
        try:
            price = market_data.get_price(m["symbol"])
            day_change_pct = None
            if price.get("ltp") and price.get("prev_close"):
                day_change_pct = round(
                    (price["ltp"] - price["prev_close"]) / price["prev_close"] * 100, 2
                )
            enriched.append({
                **m,
                "ltp": price.get("ltp"),
                "day_change_pct": day_change_pct,
                "volume": price.get("volume"),
            })
        except Exception:
            enriched.append({**m, "ltp": None, "day_change_pct": None, "volume": None})
    return {"results": enriched}


@app.post("/watchlist")
def add_to_watchlist(body: AddSymbolBody):
    if body.symbol not in SYMBOL_INDEX:
        raise HTTPException(400, f"Unknown symbol: {body.symbol}")
    with database.get_conn() as conn:
        conn.execute(
            """INSERT INTO watchlist_items (device_id, symbol, added_at)
               VALUES (?, ?, ?)
               ON CONFLICT(device_id, symbol) DO NOTHING""",
            (body.device_id, body.symbol, datetime.now(timezone.utc).isoformat()),
        )
    return {"ok": True}


@app.delete("/watchlist/{symbol}")
def remove_from_watchlist(symbol: str, device_id: str = Query(...)):
    with database.get_conn() as conn:
        conn.execute(
            "DELETE FROM watchlist_items WHERE device_id = ? AND symbol = ?",
            (device_id, symbol),
        )
        conn.execute(
            "DELETE FROM last_seen WHERE device_id = ? AND symbol = ?",
            (device_id, symbol),
        )
    return {"ok": True}


@app.get("/watchlist")
def get_watchlist(device_id: str = Query(...)):
    with database.get_conn() as conn:
        symbols = [
            r["symbol"] for r in conn.execute(
                "SELECT symbol FROM watchlist_items WHERE device_id = ? ORDER BY added_at",
                (device_id,),
            ).fetchall()
        ]
        last_seen_rows = {
            r["symbol"]: dict(r) for r in conn.execute(
                "SELECT * FROM last_seen WHERE device_id = ?", (device_id,)
            ).fetchall()
        }

    items = []
    now_iso = datetime.now(timezone.utc).isoformat()

    index_day_change_pct = None
    try:
        index_price = market_data.get_price(NIFTY_INDEX_SYMBOL)
        if index_price.get("ltp") and index_price.get("prev_close"):
            index_day_change_pct = round(
                (index_price["ltp"] - index_price["prev_close"]) / index_price["prev_close"] * 100, 2
            )
    except Exception:
        pass

    for symbol in symbols:
        try:
            price = market_data.get_price(symbol)
        except Exception:
            items.append({
                "symbol": symbol,
                "name": SYMBOL_INDEX[symbol]["name"],
                "error": "Data unavailable right now",
            })
            continue

        day_change_pct = round(
            (price["ltp"] - price["prev_close"]) / price["prev_close"] * 100, 2
        ) if price.get("ltp") and price.get("prev_close") else None

        flags = change_detection.compute_flags(price)
        benchmark_flag = change_detection.compute_benchmark_flag(day_change_pct, index_day_change_pct)
        if benchmark_flag:
            flags.append(benchmark_flag)

        diff = change_detection.compute_diff(price, last_seen_rows.get(symbol))

        item_news = None
        if any(f["type"] in ("big_move", "gap") for f in flags):
            try:
                item_news = news.fetch_headline(symbol, SYMBOL_INDEX[symbol]["name"])
            except Exception:
                item_news = None

        items.append({
            "symbol": symbol,
            "name": SYMBOL_INDEX[symbol]["name"],
            "sector": SYMBOL_INDEX[symbol]["sector"],
            "ltp": price.get("ltp"),
            "prev_close": price.get("prev_close"),
            "day_change_pct": day_change_pct,
            "day_high": price.get("day_high"),
            "day_low": price.get("day_low"),
            "volume": price.get("volume"),
            "week52_high": price.get("week52_high"),
            "week52_low": price.get("week52_low"),
            "sparkline": price.get("sparkline", []),
            "is_market_open": bool(price.get("is_market_open")),
            "data_as_of": price.get("updated_at"),
            "stale": price.get("stale", False),
            "flags": flags,
            "diff": diff,
            "news": item_news,
        })

        with database.get_conn() as conn:
            conn.execute(
                """INSERT INTO last_seen
                   (device_id, symbol, ltp, day_high, day_low, volume,
                    week52_high, week52_low, seen_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(device_id, symbol) DO UPDATE SET
                     ltp=excluded.ltp, day_high=excluded.day_high, day_low=excluded.day_low,
                     volume=excluded.volume, week52_high=excluded.week52_high,
                     week52_low=excluded.week52_low, seen_at=excluded.seen_at""",
                (device_id, symbol, price.get("ltp"), price.get("day_high"),
                 price.get("day_low"), price.get("volume"), price.get("week52_high"),
                 price.get("week52_low"), now_iso),
            )

    def sort_key(item):
        if item.get("error"):
            return (-1, 0)
        return (1, change_detection.compute_attention_score(item))

    items.sort(key=sort_key, reverse=True)

    digest = change_detection.build_digest(items)
    insight = portfolio_insights.compute_portfolio_insight(items)
    return {"digest": digest, "items": items, "insight": insight}


@app.get("/health")
def health():
    return {"status": "ok", "market_open": market_data.is_market_open()}