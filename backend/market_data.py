"""
Market data layer.

Design: read-through cache, keyed by symbol (not by device). Two TTLs:

  LIVE_TTL_SECONDS   - how fresh ltp/open/day_high/day_low/volume must be.
                       Short while market is open, long while it's closed.

  STATS_TTL_SECONDS  - how fresh 52w high/low, 20d avg volume, and daily
                       volatility must be. These move slowly, refreshed
                       ~once a day.
"""

from datetime import datetime, timezone, timedelta
import statistics
import json
from database import get_conn

IST = timezone(timedelta(hours=5, minutes=30))

LIVE_TTL_SECONDS_OPEN = 15
LIVE_TTL_SECONDS_CLOSED = 3600
STATS_TTL_SECONDS = 24 * 3600


def _to_yahoo_symbol(symbol: str) -> str:
    """NSE equities need a .NS suffix; index symbols like ^NSEI (Nifty 50)
    are already in Yahoo's native format and must NOT get one."""
    return symbol if symbol.startswith("^") else f"{symbol}.NS"


def is_market_open(now: datetime | None = None) -> bool:
    now = now or datetime.now(IST)
    if now.weekday() >= 5:
        return False
    open_t = now.replace(hour=9, minute=15, second=0, microsecond=0)
    close_t = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return open_t <= now <= close_t


def _fetch_live_from_yfinance(symbol: str) -> dict:
    import yfinance as yf
    ticker = yf.Ticker(_to_yahoo_symbol(symbol))
    fi = ticker.fast_info
    return {
        "ltp": float(fi["last_price"]),
        "prev_close": float(fi["previous_close"]),
        "open": float(fi["open"]),
        "day_high": float(fi["day_high"]),
        "day_low": float(fi["day_low"]),
        "volume": int(fi["last_volume"]),
    }


def _fetch_stats_from_yfinance(symbol: str) -> dict:
    import yfinance as yf
    ticker = yf.Ticker(_to_yahoo_symbol(symbol))
    hist = ticker.history(period="1y")
    if hist.empty:
        raise ValueError(f"no history for {symbol}")

    week52_high = float(hist["High"].max())
    week52_low = float(hist["Low"].min())
    avg_volume_20d = float(hist["Volume"].tail(20).mean())

    closes = hist["Close"].tail(90).tolist()
    daily_returns_pct = [
        (closes[i] - closes[i - 1]) / closes[i - 1] * 100
        for i in range(1, len(closes))
        if closes[i - 1] != 0
    ]
    daily_volatility_pct = statistics.pstdev(daily_returns_pct) if len(daily_returns_pct) > 1 else 2.0

    sparkline = [round(c, 2) for c in hist["Close"].tail(30).tolist()]

    return {
        "week52_high": week52_high,
        "week52_low": week52_low,
        "avg_volume_20d": avg_volume_20d,
        "daily_volatility_pct": round(daily_volatility_pct, 3),
        "sparkline_json": json.dumps(sparkline),
    }


def get_price(symbol: str) -> dict:
    now = datetime.now(timezone.utc)
    market_open = is_market_open()
    live_ttl = LIVE_TTL_SECONDS_OPEN if market_open else LIVE_TTL_SECONDS_CLOSED

    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM price_cache WHERE symbol = ?", (symbol,)
        ).fetchone()

        needs_live = row is None or _age_seconds(row["updated_at"], now) > live_ttl
        needs_stats = row is None or row["week52_high"] is None or \
            _age_seconds(row["stats_updated_at"], now) > STATS_TTL_SECONDS

        live_data, stats_data = None, None
        stale = False

        if needs_live:
            try:
                live_data = _fetch_live_from_yfinance(symbol)
            except Exception:
                stale = True

        if needs_stats:
            try:
                stats_data = _fetch_stats_from_yfinance(symbol)
            except Exception:
                pass

        if live_data is None and row is None:
            raise RuntimeError(f"no data available for {symbol}")

        merged = dict(row) if row else {}
        if live_data:
            merged.update(live_data)
            merged["updated_at"] = now.isoformat()
            merged["source"] = "live"
        elif needs_live and row:
            # we needed a fresh price, tried, and the fetch failed --
            # THIS is genuine staleness, worth surfacing to the user.
            merged["source"] = "stale_fallback"
            stale = True
        # else: needs_live was False, meaning the cache is still within
        # its TTL and serving it is the correct, intentional behavior --
        # not staleness.

        if stats_data:
            merged.update(stats_data)
            merged["stats_updated_at"] = now.isoformat()

        merged["is_market_open"] = int(market_open)
        merged["symbol"] = symbol

        # Defensive: guarantee every column the INSERT references actually
        # exists in `merged`, even if a live/stats fetch returned a partial
        # dict. Without this, a missing key here would raise deep inside
        # sqlite3's parameter binding instead of failing gracefully.
        for col in ("ltp", "prev_close", "open", "day_high", "day_low", "volume",
                    "avg_volume_20d", "week52_high", "week52_low",
                    "daily_volatility_pct", "sparkline_json", "updated_at",
                    "stats_updated_at", "source"):
            merged.setdefault(col, None)

        conn.execute(
            """INSERT INTO price_cache
               (symbol, ltp, prev_close, open, day_high, day_low, volume,
                avg_volume_20d, week52_high, week52_low, daily_volatility_pct,
                sparkline_json, updated_at, stats_updated_at, is_market_open, source)
               VALUES (:symbol, :ltp, :prev_close, :open, :day_high, :day_low, :volume,
                       :avg_volume_20d, :week52_high, :week52_low, :daily_volatility_pct,
                       :sparkline_json, :updated_at, :stats_updated_at, :is_market_open, :source)
               ON CONFLICT(symbol) DO UPDATE SET
                 ltp=excluded.ltp, prev_close=excluded.prev_close, open=excluded.open,
                 day_high=excluded.day_high, day_low=excluded.day_low, volume=excluded.volume,
                 avg_volume_20d=excluded.avg_volume_20d, week52_high=excluded.week52_high,
                 week52_low=excluded.week52_low, daily_volatility_pct=excluded.daily_volatility_pct,
                 sparkline_json=excluded.sparkline_json,
                 updated_at=excluded.updated_at, stats_updated_at=excluded.stats_updated_at,
                 is_market_open=excluded.is_market_open, source=excluded.source
            """,
            merged,
        )

        merged["stale"] = stale
        merged["sparkline"] = json.loads(merged.get("sparkline_json") or "[]")
        return merged


def _age_seconds(iso_ts, now) -> float:
    if not iso_ts:
        return float("inf")
    ts = datetime.fromisoformat(iso_ts)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds()