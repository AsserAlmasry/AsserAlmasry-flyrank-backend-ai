"""Postgres implementation of TaskRepository. Same methods, same return shapes."""
import psycopg
from psycopg.rows import dict_row

COLUMNS = "id, title, done"


class PostgresTaskRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def _conn(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def list(self) -> list[dict]:
        with self._conn() as conn:
            return conn.execute(f"SELECT {COLUMNS} FROM tasks ORDER BY id").fetchall()

    def get(self, task_id: int) -> dict | None:
        with self._conn() as conn:
            return conn.execute(f"SELECT {COLUMNS} FROM tasks WHERE id = %s", (task_id,)).fetchone()

    def create(self, title: str) -> dict:
        with self._conn() as conn:
            return conn.execute(
                f"INSERT INTO tasks (title) VALUES (%s) RETURNING {COLUMNS}", (title,)
            ).fetchone()

    def update(self, task_id: int, title: str | None, done: bool | None) -> dict | None:
        with self._conn() as conn:
            return conn.execute(
                f"""UPDATE tasks
                       SET title = COALESCE(%s, title),
                           done  = COALESCE(%s, done)
                     WHERE id = %s
                 RETURNING {COLUMNS}""",
                (title, done, task_id),
            ).fetchone()

    def delete(self, task_id: int) -> bool:
        with self._conn() as conn:
            return conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,)).rowcount > 0
