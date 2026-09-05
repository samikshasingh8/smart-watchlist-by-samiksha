"""
SQLite persistence layer.

Three tables:
  watchlist_items  -> which symbols a device is watching
  price_cache      -> ONE row per symbol, shared across every device.
                      This is what makes the system scale: 1000 devices
                      watching RELIANCE still means one upstream fetch,
                      not 1000.
  last_seen        -> ONE row per (device_id, symbol). The snapshot of
                      what a device saw the last time it loaded its
                      watchlist. This is the baseline the diff engine
                      compares "now" against.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "watchlist.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    added_at    TEXT NOT NULL,
    UNIQUE(device_id, symbol)
);

CREATE TABLE IF NOT EXISTS price_cache (
    symbol                  TEXT PRIMARY KEY,
    ltp                     REAL,
    prev_close              REAL,
    open                    REAL,
    day_high                REAL,
    day_low                 REAL,
    volume                  INTEGER,
    avg_volume_20d          REAL,
    week52_high             REAL,
    week52_low              REAL,
    daily_volatility_pct    REAL,
    sparkline_json          TEXT,
    updated_at              TEXT,
    stats_updated_at        TEXT,
    is_market_open          INTEGER DEFAULT 0,
    source                  TEXT DEFAULT 'live'
);

CREATE TABLE IF NOT EXISTS last_seen (
    device_id       TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    ltp             REAL,
    day_high        REAL,
    day_low         REAL,
    volume          INTEGER,
    week52_high     REAL,
    week52_low      REAL,
    seen_at         TEXT,
    PRIMARY KEY (device_id, symbol)
);

CREATE TABLE IF NOT EXISTS news_cache (
    symbol      TEXT PRIMARY KEY,
    headline    TEXT,
    link        TEXT,
    fetched_at  TEXT
);
"""



def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()