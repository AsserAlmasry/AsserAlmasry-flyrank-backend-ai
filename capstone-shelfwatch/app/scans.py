"""A scan: fetch the competitor catalogue politely, store every title, and record what changed since last time."""
import hashlib
import logging
import re

from pydantic import BaseModel, Field, ValidationError

from . import cache, config, db
from .scraper.fetch import Fetcher, FetchError
from .scraper.parse import parse_book, parse_catalogue

log = logging.getLogger("shelfwatch.scan")
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


class ScrapedBook(BaseModel):
    """What one book page must contain before it is allowed into the database."""
    url: str = Field(pattern=r"^https?://")
    title: str = Field(min_length=1)
    price: float = Field(gt=0, lt=10_000)
    in_stock: bool
    available_count: int | None = Field(default=None, ge=0)
    rating: int | None = Field(default=None, ge=1, le=5)
    description: str | None = None


def normalize(url: str, raw: dict) -> ScrapedBook:
    price = re.search(r"\d+(?:\.\d+)?", (raw.get("price_text") or "").replace(",", ""))
    avail = raw.get("availability_text") or ""
    count = re.search(r"\((\d+) available\)", avail)
    return ScrapedBook(
        url=url,
        title=raw.get("title") or "",
        price=float(price.group()) if price else 0,
        in_stock=avail.lower().startswith("in stock"),
        available_count=int(count.group(1)) if count else None,
        rating=RATINGS.get(raw.get("rating_text") or ""),
        description=raw.get("description"),
    )


def demo_drift(book: ScrapedBook, scan_id: int) -> ScrapedBook:
    """DEMO ONLY (DEMO_DRIFT=1). The practice site never changes, so this simulates small, repeatable moves
    (about 1 in 7 prices moves 1-5%, about 1 in 23 titles flips stock) to show change detection working."""
    h = int(hashlib.sha1(f"{book.url}:{scan_id}".encode()).hexdigest(), 16)
    update = {}
    if h % 7 == 0:
        pct = (h % 5 + 1) / 100 * (1 if h % 2 else -1)
        update["price"] = round(book.price * (1 + pct), 2)
    if h % 23 == 0:
        update["in_stock"] = not book.in_stock
        update["available_count"] = 0 if book.in_stock else 3
    return book.model_copy(update=update)


def create_scan(pages: int, triggered_by: str) -> int:
    with db.tx() as conn:
        return conn.execute("INSERT INTO scans (status, pages, triggered_by, created_at) VALUES ('queued', ?, ?, ?)",
                            (pages, triggered_by, db.now())).lastrowid


def collect(fetcher: Fetcher, pages: int) -> tuple[list[ScrapedBook], int]:
    """Discover up to `pages` catalogue pages by following the site's own "next" link, then read every book page."""
    urls, url, failed = [], config.TARGET_START_URL, 0
    for n in range(1, pages + 1):
        if not url:
            break
        try:
            page = fetcher.get(url, cache_name=f"catalogue-page-{n}.html")
        except FetchError as exc:
            log.warning("catalogue page failed: %s", exc)
            failed += 1
            break
        links, url = parse_catalogue(page.html, page.url)
        urls += [u for u in links if u not in urls]
    books = []
    for u in urls:
        try:  # one bad page is logged and skipped, never fatal
            books.append(normalize(u, parse_book(fetcher.get(u).html)))
        except (FetchError, ValueError, ValidationError) as exc:
            log.warning("skipping %s: %s", u, exc)
            failed += 1
    return books, failed


def store(conn, scan_id: int, books: list[ScrapedBook]) -> tuple[int, int, list[int]]:
    """Upsert books, add one snapshot each, and write a change row for every difference. Returns
    (new_books, changes, ids_needing_enrichment)."""
    ts, new_count, change_count, to_enrich = db.now(), 0, 0, []

    def change(book_id, kind, old, new):
        nonlocal change_count
        change_count += 1
        conn.execute("INSERT INTO changes (book_id, scan_id, kind, old_value, new_value, detected_at) VALUES (?,?,?,?,?,?)",
                     (book_id, scan_id, kind, None if old is None else str(old), None if new is None else str(new), ts))

    for b in books:
        old = conn.execute("SELECT * FROM books WHERE url = ?", (b.url,)).fetchone()
        if old is None:
            book_id = conn.execute(
                """INSERT INTO books (url, title, description, rating, price, in_stock, available_count, first_seen, last_seen)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (b.url, b.title, b.description, b.rating, b.price, int(b.in_stock), b.available_count, ts, ts)).lastrowid
            new_count += 1
            change(book_id, "new", None, b.price)
            to_enrich.append(book_id)
        else:
            book_id = old["id"]
            if b.price > old["price"]:
                change(book_id, "price_up", old["price"], b.price)
            elif b.price < old["price"]:
                change(book_id, "price_down", old["price"], b.price)
            if old["in_stock"] and not b.in_stock:
                change(book_id, "out_of_stock", "in stock", "out of stock")
            elif not old["in_stock"] and b.in_stock:
                change(book_id, "back_in_stock", "out of stock", "in stock")
            if (old["description"] or "") != (b.description or "") or (old["title"] != b.title):
                to_enrich.append(book_id)
            conn.execute("""UPDATE books SET title=?, description=?, rating=?, price=?, in_stock=?, available_count=?,
                            last_seen=? WHERE id=?""",
                         (b.title, b.description, b.rating, b.price, int(b.in_stock), b.available_count, ts, book_id))
        conn.execute("""INSERT OR REPLACE INTO snapshots (book_id, scan_id, price, in_stock, available_count, seen_at)
                        VALUES (?,?,?,?,?,?)""", (book_id, scan_id, b.price, int(b.in_stock), b.available_count, ts))
    return new_count, change_count, to_enrich


def run_scan(scan_id: int, fetcher: Fetcher | None = None) -> None:
    """The background job. Safe to call from a thread; every outcome ends up in the scans table."""
    with db.tx() as conn:
        conn.execute("UPDATE scans SET status='running', started_at=? WHERE id=?", (db.now(), scan_id))
        pages = conn.execute("SELECT pages FROM scans WHERE id=?", (scan_id,)).fetchone()["pages"]
    fetcher = fetcher or Fetcher(config.CACHE_DIR, max_age_hours=config.PAGE_CACHE_HOURS)
    try:
        books, failed = collect(fetcher, pages)
        if config.DEMO_DRIFT:
            books = [demo_drift(b, scan_id) for b in books]
        with db.tx() as conn:
            new_count, change_count, to_enrich = store(conn, scan_id, books)
            # Backlog: titles whose enrichment failed earlier (e.g. provider down) are retried on every scan.
            missing = [r["id"] for r in conn.execute(
                "SELECT b.id FROM books b LEFT JOIN enrichments e ON e.book_id = b.id WHERE e.book_id IS NULL")]
            to_enrich = list(dict.fromkeys(to_enrich + missing))
        from .enrich import enrich_books  # local import: keeps the scan usable even if the LLM layer is misconfigured
        enrich_books(to_enrich)
        cache.stats_cache.clear()  # the dashboard numbers just changed
        with db.tx() as conn:
            conn.execute("""UPDATE scans SET status='done', finished_at=?, books_seen=?, new_books=?, changes=?,
                            pages_fetched=?, cache_hits=?, failed_pages=? WHERE id=?""",
                         (db.now(), len(books), new_count, change_count, fetcher.stats["pages_fetched"],
                          fetcher.stats["cache_hits"], failed, scan_id))
        log.info("scan %s done: %s books, %s new, %s changes", scan_id, len(books), new_count, change_count)
    except Exception as exc:  # a background job must never die silently
        log.exception("scan %s failed", scan_id)
        with db.tx() as conn:
            conn.execute("UPDATE scans SET status='failed', finished_at=?, error=? WHERE id=?",
                         (db.now(), f"{type(exc).__name__}: {exc}", scan_id))
