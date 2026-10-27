"""Bookstore PDF reports: query -> render -> store -> serve by link."""
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from db import BASE, connect
from render import render_pdf

REPORTS_DIR = BASE / "reports"

app = FastAPI(title="Bookstore PDF Reports")


def init_reports_table() -> None:
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS reports (
                            id         INTEGER PRIMARY KEY AUTOINCREMENT,
                            path       TEXT NOT NULL,
                            created_at TEXT NOT NULL
                        )""")


init_reports_table()


def to_json(row) -> dict:
    return {"id": row["id"], "created_at": row["created_at"], "file": f"/reports/{row['id']}/file"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reports", status_code=201)
async def create_report():
    # The whole pipeline runs right here in the request: query -> render -> store. It takes a few seconds.
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect() as conn:
        report_id = conn.execute("INSERT INTO reports (path, created_at) VALUES ('', ?)", (created_at,)).lastrowid
    path = REPORTS_DIR / f"{report_id}.pdf"
    await render_pdf(path)
    with connect() as conn:
        conn.execute("UPDATE reports SET path = ? WHERE id = ?", (str(path.relative_to(BASE)), report_id))
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    return to_json(row)


@app.get("/reports/{report_id}")
def get_report(report_id: int):
    with connect() as conn:
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if row is None:
        return JSONResponse(status_code=404, content={"error": f"Report {report_id} not found"})
    return to_json(row)


@app.get("/reports/{report_id}/file")
def get_report_file(report_id: int):
    # The only endpoint that moves the bytes: "store and link".
    with connect() as conn:
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if row is None or not row["path"] or not (BASE / row["path"]).exists():
        return JSONResponse(status_code=404, content={"error": f"Report {report_id} file not found"})
    return FileResponse(BASE / row["path"], media_type="application/pdf", filename=Path(row["path"]).name)
