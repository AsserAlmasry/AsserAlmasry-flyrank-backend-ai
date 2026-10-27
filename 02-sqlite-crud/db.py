"""Storage layer: everything that knows about SQLite lives in this file."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "tasks.db"

SEED = [("Read the assignment", 1), ("Build the CRUD API", 0), ("Push to GitHub", 0)]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the table if missing; insert the 3 example tasks only if the table is empty."""
    with connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                   id    INTEGER PRIMARY KEY AUTOINCREMENT,
                   title TEXT    NOT NULL,
                   done  BOOLEAN NOT NULL DEFAULT 0
               )"""
        )
        (count,) = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()
        if count == 0:
            conn.executemany("INSERT INTO tasks (title, done) VALUES (?, ?)", SEED)
