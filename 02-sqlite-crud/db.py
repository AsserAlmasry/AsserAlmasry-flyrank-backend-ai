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


def row_to_task(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


class TaskRepository:
    """All SQL for tasks. The routes only ever call these methods."""

    def list(self) -> list[dict]:
        with connect() as conn:
            rows = conn.execute("SELECT id, title, done FROM tasks ORDER BY id").fetchall()
        return [row_to_task(r) for r in rows]

    def get(self, task_id: int) -> dict | None:
        with connect() as conn:
            row = conn.execute("SELECT id, title, done FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return row_to_task(row) if row else None

    def create(self, title: str) -> dict:
        with connect() as conn:
            cur = conn.execute("INSERT INTO tasks (title, done) VALUES (?, 0)", (title,))
            new_id = cur.lastrowid
        return self.get(new_id)

    def update(self, task_id: int, title: str | None = None, done: bool | None = None) -> dict | None:
        if self.get(task_id) is None:
            return None
        with connect() as conn:
            if title is not None:
                conn.execute("UPDATE tasks SET title = ? WHERE id = ?", (title, task_id))
            if done is not None:
                conn.execute("UPDATE tasks SET done = ? WHERE id = ?", (int(done), task_id))
        return self.get(task_id)

    def delete(self, task_id: int) -> bool:
        with connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cur.rowcount > 0
