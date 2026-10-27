"""SQLite storage. The schema is created on startup; the data survives restarts."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    status       TEXT NOT NULL CHECK (status IN ('queued','running','done','failed')),
    pages        INTEGER NOT NULL,
    triggered_by TEXT NOT NULL,
    started_at   TEXT,
    finished_at  TEXT,
    books_seen   INTEGER DEFAULT 0,
    new_books    INTEGER DEFAULT 0,
    changes      INTEGER DEFAULT 0,
    pages_fetched INTEGER DEFAULT 0,
    cache_hits   INTEGER DEFAULT 0,
    failed_pages INTEGER DEFAULT 0,
    error        TEXT,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS books (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    description     TEXT,
    rating          INTEGER,
    price           REAL NOT NULL,
    in_stock        INTEGER NOT NULL,
    available_count INTEGER,
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id         INTEGER NOT NULL REFERENCES books(id),
    scan_id         INTEGER NOT NULL REFERENCES scans(id),
    price           REAL NOT NULL,
    in_stock        INTEGER NOT NULL,
    available_count INTEGER,
    seen_at         TEXT NOT NULL,
    UNIQUE (book_id, scan_id)
);
CREATE TABLE IF NOT EXISTS changes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id     INTEGER NOT NULL REFERENCES books(id),
    scan_id     INTEGER NOT NULL REFERENCES scans(id),
    kind        TEXT NOT NULL CHECK (kind IN ('new','price_up','price_down','out_of_stock','back_in_stock')),
    old_value   TEXT,
    new_value   TEXT,
    detected_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS enrichments (
    book_id        INTEGER PRIMARY KEY REFERENCES books(id),
    content_hash   TEXT NOT NULL,
    category       TEXT NOT NULL,
    summary        TEXT NOT NULL,
    confidence     REAL NOT NULL,
    model          TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    path        TEXT NOT NULL,
    report_date TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    triggered_by TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_changes_detected ON changes (detected_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_book ON snapshots (book_id, seen_at);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def tx():
    """One transaction: commit on success, roll back on error, always close."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with tx() as conn:
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode = WAL")  # API reads while a background scan writes
