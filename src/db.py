"""SQLite 읽기/쓰기 (요구사항 5장)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "finsight.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS stocks (
    code   TEXT PRIMARY KEY,
    name   TEXT NOT NULL,
    market TEXT
);
CREATE TABLE IF NOT EXISTS prices (
    code   TEXT NOT NULL,
    date   TEXT NOT NULL,
    open   REAL, high REAL, low REAL, close REAL, volume INTEGER,
    PRIMARY KEY (code, date)
);
CREATE TABLE IF NOT EXISTS fundamentals (
    code       TEXT NOT NULL,
    date       TEXT NOT NULL,
    market_cap REAL, per REAL, pbr REAL, high_52w REAL, low_52w REAL,
    PRIMARY KEY (code, date)
);
CREATE TABLE IF NOT EXISTS news (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT NOT NULL,
    title        TEXT NOT NULL,
    press        TEXT,
    published_at TEXT,
    url          TEXT NOT NULL UNIQUE,
    body         TEXT
);
CREATE TABLE IF NOT EXISTS analysis (
    news_id     INTEGER PRIMARY KEY REFERENCES news(id) ON DELETE CASCADE,
    summary     TEXT,
    sentiment   TEXT,
    confidence  REAL,
    analyzed_at TEXT
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE INDEX IF NOT EXISTS idx_news_code ON news(code, published_at);
"""


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------- stocks ----------
def save_stocks(conn, rows: list[tuple[str, str, str]]) -> None:
    conn.executemany(
        "INSERT INTO stocks(code, name, market) VALUES (?, ?, ?) "
        "ON CONFLICT(code) DO UPDATE SET name=excluded.name, market=excluded.market",
        rows,
    )
    conn.commit()


def count_stocks(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]


def get_stock(conn, code: str):
    return conn.execute("SELECT * FROM stocks WHERE code = ?", (code,)).fetchone()


def find_stock_by_name(conn, name: str):
    row = conn.execute("SELECT * FROM stocks WHERE name = ?", (name,)).fetchone()
    if row is None:  # 대소문자/공백 차이 허용 (예: "naver" → "NAVER")
        row = conn.execute(
            "SELECT * FROM stocks WHERE REPLACE(UPPER(name), ' ', '') = ?",
            (name.replace(" ", "").upper(),),
        ).fetchone()
    return row


def search_stock_names(conn, keyword: str, limit: int = 10) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM stocks WHERE name LIKE ? ORDER BY LENGTH(name) LIMIT ?",
        (f"%{keyword}%", limit),
    ).fetchall()


# ---------- prices ----------
def save_prices(conn, code: str, df: pd.DataFrame) -> None:
    """df: index=날짜, columns=open/high/low/close/volume"""
    rows = [
        (code, idx.strftime("%Y-%m-%d"), float(r.open), float(r.high), float(r.low), float(r.close),
         int(r.volume))
        for idx, r in df.iterrows()
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO prices(code, date, open, high, low, close, volume) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()


def load_prices(conn, code: str, start: str | None = None) -> pd.DataFrame:
    sql = "SELECT date, open, high, low, close, volume FROM prices WHERE code = ?"
    params: list = [code]
    if start:
        sql += " AND date >= ?"
        params.append(start)
    df = pd.read_sql_query(sql + " ORDER BY date", conn, params=params)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    return df


# ---------- fundamentals ----------
def save_fundamentals(conn, code: str, date: str, f: dict) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO fundamentals(code, date, market_cap, per, pbr, high_52w, low_52w) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (code, date, f.get("market_cap"), f.get("per"), f.get("pbr"), f.get("high_52w"), f.get("low_52w")),
    )
    conn.commit()


def load_latest_fundamentals(conn, code: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM fundamentals WHERE code = ? ORDER BY date DESC LIMIT 1", (code,)
    ).fetchone()
    return dict(row) if row else None


# ---------- news / analysis ----------
def news_exists(conn, url: str) -> bool:
    return conn.execute("SELECT 1 FROM news WHERE url = ?", (url,)).fetchone() is not None


def save_news(conn, code: str, item: dict) -> int | None:
    """같은 URL은 저장하지 않는다. 새로 저장했으면 id, 아니면 None."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO news(code, title, press, published_at, url, body) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (code, item["title"], item.get("press"), item.get("published_at"), item["url"], item.get("body")),
    )
    conn.commit()
    return cur.lastrowid if cur.rowcount else None


def load_news(conn, code: str, limit: int = 5) -> list[dict]:
    rows = conn.execute(
        "SELECT n.*, a.summary, a.sentiment, a.confidence, a.analyzed_at "
        "FROM news n LEFT JOIN analysis a ON a.news_id = n.id "
        "WHERE n.code = ? ORDER BY n.published_at DESC LIMIT ?",
        (code, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def save_analysis(conn, news_id: int, summary: str, sentiment: str, confidence: float) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO analysis(news_id, summary, sentiment, confidence, analyzed_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (news_id, summary, sentiment, confidence, now_str()),
    )
    conn.commit()


# ---------- meta ----------
def set_meta(conn, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, value))
    conn.commit()


def get_meta(conn, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def cached_stock_list(conn) -> list[dict]:
    """시세가 캐시된 종목과 마지막 갱신 시각 (FR-8, FR-9)."""
    rows = conn.execute(
        "SELECT s.code, s.name, s.market, m.value AS updated_at "
        "FROM stocks s JOIN meta m ON m.key = 'updated:' || s.code "
        "ORDER BY m.value DESC"
    ).fetchall()
    return [dict(r) for r in rows]
