"""Bookstore PDF reports: query -> render -> store -> serve by link."""
import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from db import BASE, connect
from render import render_pdf

REPORTS_DIR = BASE / "reports"

app = FastAPI(title="Bookstore PDF Reports")

# Two clicks can arrive at the *same* moment: without a lock both would see "no report today" and both
# would render. The lock makes check-then-create one step (fine for one server process; with several
# processes you'd use a UNIQUE constraint on report_date in the database instead).
generate_lock = asyncio.Lock()


class ReportRequest(BaseModel):
    force: bool = False  # true -> always make a fresh report, skip the once-per-day check


def init_reports_table() -> None:
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS reports (
                            id         INTEGER PRIMARY KEY AUTOINCREMENT,
                            path        TEXT NOT NULL,
                            created_at  TEXT NOT NULL,
                            report_date TEXT NOT NULL
                        )""")


init_reports_table()


def to_json(row) -> dict:
    return {"id": row["id"], "created_at": row["created_at"], "file": f"/reports/{row['id']}/file"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reports", status_code=201)
async def create_report(body: ReportRequest | None = None):
    force = bool(body and body.force)
    async with generate_lock:
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        if not force:  # idempotency: one report per day, however many times the button is clicked
            with connect() as conn:
                existing = conn.execute(
                    "SELECT * FROM reports WHERE report_date = ? AND path != '' ORDER BY id DESC LIMIT 1", (today,)
                ).fetchone()
            if existing is not None:
                return JSONResponse(status_code=200, content=to_json(existing))

        # The whole pipeline runs right here in the request: query -> render -> store. It takes a moment.
        with connect() as conn:
            report_id = conn.execute("INSERT INTO reports (path, created_at, report_date) VALUES ('', ?, ?)",
                                     (now.isoformat(timespec="seconds"), today)).lastrowid
        path = REPORTS_DIR / f"{report_id}.pdf"
        try:
            await render_pdf(path)
        except Exception:
            with connect() as conn:  # don't leave a row pointing at a file that was never written
                conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
            raise
        with connect() as conn:
            conn.execute("UPDATE reports SET path = ? WHERE id = ?", (str(path.relative_to(BASE)), report_id))
            row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    return to_json(row)


@app.get("/reports")
def list_reports():
    """Extra: the control panel, every generated report with its link."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM reports WHERE path != '' ORDER BY id DESC").fetchall()
    return [to_json(r) for r in rows]


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
    nice_name = f"bookstore-report-{row['report_date']}-{row['id']}.pdf"  # extra: a professional download name
    return FileResponse(BASE / row["path"], media_type="application/pdf", filename=nice_name)
