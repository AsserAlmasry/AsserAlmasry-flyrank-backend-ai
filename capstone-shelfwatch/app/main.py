"""ShelfWatch API.  Run:  uvicorn app.main:app --port 8000   (docs at /docs)"""
import logging
import re
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import auth, cache, config, db, reports, scans, scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    auth.secret()  # fail fast at startup if JWT_SECRET is missing or weak
    sched = scheduler.start()
    yield
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(
    title="ShelfWatch",
    version="1.0",
    description="Competitor price & stock monitor. Sign up, log in, click **Authorize**, then start a scan.",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def bad_input(_: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p not in ("body", "query")) or "body"
    return JSONResponse(status_code=400, content={"error": f"Invalid '{field}': {first['msg']}"})


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail}, headers=getattr(exc, "headers", None))


# ------------------------------------------------------------------ public

class Credentials(BaseModel):
    email: str = Field(examples=["owner@myshop.test"])
    password: str = Field(examples=["a-long-password"])


@app.get("/health", tags=["public"])
def health():
    return {"status": "ok"}


@app.post("/auth/signup", status_code=201, tags=["auth"])
def signup(body: Credentials):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "email is not valid")
    if len(body.password) < 10:
        raise HTTPException(400, "password must be at least 10 characters")
    try:
        with db.tx() as conn:
            uid = conn.execute("INSERT INTO users (email, password_hash, created_at) VALUES (?,?,?)",
                               (email, auth.hash_password(body.password), db.now())).lastrowid
    except db.sqlite3.IntegrityError:
        raise HTTPException(409, "an account with this email already exists")
    return {"id": uid, "email": email}


@app.post("/auth/login", tags=["auth"])
def login(body: Credentials):
    with db.tx() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (body.email.strip().lower(),)).fetchone()
    # Same message whether the email or the password is wrong: don't tell attackers which emails exist.
    if user is None or not auth.verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    return auth.issue_token(user["id"], user["email"])


# ------------------------------------------------------------------ protected

@app.get("/me", tags=["auth"])
def me(user: auth.CurrentUser):
    return user


class ScanRequest(BaseModel):
    pages: int = Field(default=config.SCAN_PAGES, ge=1, le=5, description="Catalogue pages to scan (20 titles each)")


@app.post("/scans", status_code=202, tags=["scans"])
def start_scan(user: auth.CurrentUser, background: BackgroundTasks, body: ScanRequest | None = None):
    pages = (body or ScanRequest()).pages
    with db.tx() as conn:  # one scan at a time: a second click returns the running one
        running = conn.execute("SELECT id, status FROM scans WHERE status IN ('queued','running') ORDER BY id DESC").fetchone()
    if running:
        return JSONResponse(status_code=202, content={"id": running["id"], "status": running["status"], "note": "already running"})
    scan_id = scans.create_scan(pages, triggered_by=user["email"])
    background.add_task(scans.run_scan, scan_id)  # the work happens after the 202 is sent
    return {"id": scan_id, "status": "queued", "poll": f"/scans/{scan_id}"}


@app.get("/scans", tags=["scans"])
def list_scans(user: auth.CurrentUser, limit: int = Query(20, ge=1, le=100)):
    with db.tx() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,))]


@app.get("/scans/{scan_id}", tags=["scans"])
def get_scan(scan_id: int, user: auth.CurrentUser):
    with db.tx() as conn:
        row = conn.execute("SELECT * FROM scans WHERE id=?", (scan_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Scan {scan_id} not found")
    return dict(row)


@app.get("/books", tags=["catalogue"])
def list_books(
    user: auth.CurrentUser,
    q: str | None = Query(None, max_length=100, description="search in titles"),
    category: str | None = None,
    in_stock: bool | None = None,
    sort: Literal["title", "price", "price_desc", "last_change"] = "title",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    sql = """SELECT b.id, b.title, b.price, b.in_stock, b.available_count, b.rating, b.url, e.category, b.last_seen
             FROM books b LEFT JOIN enrichments e ON e.book_id = b.id WHERE 1=1"""
    params: list = []
    if q:
        sql += " AND b.title LIKE ?"
        params.append(f"%{q}%")
    if category:
        sql += " AND e.category = ?"
        params.append(category)
    if in_stock is not None:
        sql += " AND b.in_stock = ?"
        params.append(int(in_stock))
    sql += {"title": " ORDER BY b.title COLLATE NOCASE", "price": " ORDER BY b.price", "price_desc": " ORDER BY b.price DESC",
            "last_change": " ORDER BY (SELECT MAX(detected_at) FROM changes c WHERE c.book_id=b.id) DESC"}[sort]
    sql += " LIMIT ? OFFSET ?"
    with db.tx() as conn:
        return [dict(r) for r in conn.execute(sql, [*params, limit, offset])]


@app.get("/books/{book_id}", tags=["catalogue"])
def get_book(book_id: int, user: auth.CurrentUser):
    with db.tx() as conn:
        book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        if book is None:
            raise HTTPException(404, f"Book {book_id} not found")
        history = [dict(r) for r in conn.execute(
            "SELECT scan_id, price, in_stock, available_count, seen_at FROM snapshots WHERE book_id=? ORDER BY seen_at", (book_id,))]
        changes = [dict(r) for r in conn.execute(
            "SELECT kind, old_value, new_value, detected_at FROM changes WHERE book_id=? ORDER BY id DESC", (book_id,))]
        ai = conn.execute("SELECT category, summary, confidence, model, prompt_version FROM enrichments WHERE book_id=?",
                          (book_id,)).fetchone()
    return {**dict(book), "ai": dict(ai) if ai else None, "price_history": history, "changes": changes}


@app.get("/changes", tags=["catalogue"])
def list_changes(
    user: auth.CurrentUser,
    kind: Literal["new", "price_up", "price_down", "out_of_stock", "back_in_stock"] | None = None,
    include_new: bool = Query(False, description="'new' rows are noisy on the first scan; off by default"),
    limit: int = Query(50, ge=1, le=500),
):
    sql = """SELECT c.id, c.kind, c.old_value, c.new_value, c.detected_at, c.scan_id, b.id AS book_id, b.title
             FROM changes c JOIN books b ON b.id = c.book_id WHERE 1=1"""
    params: list = []
    if kind:
        sql += " AND c.kind = ?"
        params.append(kind)
    elif not include_new:
        sql += " AND c.kind != 'new'"
    sql += " ORDER BY c.id DESC LIMIT ?"
    with db.tx() as conn:
        return [dict(r) for r in conn.execute(sql, [*params, limit])]


def compute_stats() -> dict:
    with db.tx() as conn:
        totals = dict(conn.execute("""SELECT COUNT(*) AS titles, ROUND(AVG(price),2) AS avg_price, MIN(price) AS min_price,
                                      MAX(price) AS max_price, SUM(CASE WHEN in_stock THEN 0 ELSE 1 END) AS out_of_stock
                                      FROM books""").fetchone())
        totals["changes_by_kind"] = {r["kind"]: r["n"] for r in conn.execute("SELECT kind, COUNT(*) n FROM changes GROUP BY kind")}
        totals["categories"] = {r["category"]: r["n"] for r in conn.execute(
            "SELECT category, COUNT(*) n FROM enrichments GROUP BY category ORDER BY n DESC")}
        last = conn.execute("SELECT id, finished_at FROM scans WHERE status='done' ORDER BY id DESC LIMIT 1").fetchone()
        totals["last_scan"] = dict(last) if last else None
    return totals


@app.get("/stats", tags=["catalogue"])
def stats(user: auth.CurrentUser):
    value, cached = cache.stats_cache.get_or_compute("stats", compute_stats)  # cleared after every scan
    return JSONResponse(content=value, headers={"X-Cache": "HIT" if cached else "MISS"})


class ReportRequest(BaseModel):
    force: bool = False


@app.post("/reports", status_code=201, tags=["reports"])
def create_report(user: auth.CurrentUser, body: ReportRequest | None = None):
    row, created = reports.generate(triggered_by=user["email"], force=bool(body and body.force))
    payload = {"id": row["id"], "report_date": row["report_date"], "file": f"/reports/{row['id']}/file"}
    return payload if created else JSONResponse(status_code=200, content=payload)


@app.get("/reports", tags=["reports"])
def list_reports(user: auth.CurrentUser):
    with db.tx() as conn:
        return [{"id": r["id"], "report_date": r["report_date"], "triggered_by": r["triggered_by"], "file": f"/reports/{r['id']}/file"}
                for r in conn.execute("SELECT * FROM reports WHERE path != '' ORDER BY id DESC")]


@app.get("/reports/{report_id}/file", tags=["reports"])
def report_file(report_id: int, user: auth.CurrentUser):
    with db.tx() as conn:
        row = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
    if row is None or not row["path"] or not (config.REPORTS_DIR / row["path"]).exists():
        raise HTTPException(404, f"Report {report_id} not found")
    return FileResponse(config.REPORTS_DIR / row["path"], media_type="application/pdf", filename=row["path"])
