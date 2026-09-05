"""
"Why did this move?" -- a real headline for stocks that already got a
big_move or gap flag.

Approach: Google News' public RSS search feed. No signup, no API key.
Unofficial-but-public feed, not a documented API contract -- fine for
a hackathon demo, worth saying so honestly if asked.

Deliberately lazy: only called for symbols that already have a
big_move or gap flag, not for every stock on every request.
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from database import get_conn

NEWS_TTL_SECONDS = 3 * 3600
REQUEST_TIMEOUT_SECONDS = 5


def _fetch_from_google_news_rss(query: str) -> tuple[str, str] | None:
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query,
        "hl": "en-IN",
        "gl": "IN",
        "ceid": "IN:en",
    })
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)
    item = root.find("./channel/item")
    if item is None:
        return None

    title_el = item.find("title")
    link_el = item.find("link")
    if title_el is None or title_el.text is None:
        return None

    title = title_el.text
    if " - " in title:
        title = title.rsplit(" - ", 1)[0]

    link = link_el.text if link_el is not None else None
    return title, link


def fetch_headline(symbol: str, company_name: str) -> dict | None:
    now = datetime.now(timezone.utc)

    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM news_cache WHERE symbol = ?", (symbol,)
        ).fetchone()
        if row and row["fetched_at"]:
            fetched = datetime.fromisoformat(row["fetched_at"])
            if (now - fetched).total_seconds() < NEWS_TTL_SECONDS:
                return {"headline": row["headline"], "link": row["link"]} if row["headline"] else None

    headline, link = None, None
    try:
        result = _fetch_from_google_news_rss(f"{company_name} stock")
        if result:
            headline, link = result
    except Exception:
        pass

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO news_cache (symbol, headline, link, fetched_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(symbol) DO UPDATE SET
                 headline=excluded.headline, link=excluded.link, fetched_at=excluded.fetched_at""",
            (symbol, headline, link, now.isoformat()),
        )

    return {"headline": headline, "link": link} if headline else None