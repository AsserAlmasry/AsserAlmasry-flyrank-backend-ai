"""The polite scraper.

Run from the 05-polite-scraper folder:
    python -m src.main                      # normal run
    python -m src.main --with-broken-url    # Stage 5 proof: one made-up book URL is added on purpose
    python -m src.main --csv                # extra: also write output/books.csv

Pipeline: fetch -> extract -> normalize -> validate -> store -> report
"""
import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from .fetch import Fetcher, FetchError
from .models import Book, normalize
from .parse import parse_book, parse_catalogue

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "output"
START_URL = "https://books.toscrape.com/catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3
BROKEN_URL = "https://books.toscrape.com/catalogue/this-book-does-not-exist_99999/index.html"
RAW_FIELDS = ("title", "product_url", "price_text", "availability_text", "rating_text", "description",
              "source_page", "fetched_at")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def discover(fetcher: Fetcher, failures: list) -> tuple[list[tuple[str, str]], int]:
    """Follow the site's own "next" links for 3 pages. Returns ([(book_url, source_page)], pages_seen)."""
    found, url, pages = [], START_URL, 0
    while url and pages < MAX_CATALOGUE_PAGES:
        pages += 1
        try:
            page = fetcher.get(url, cache_name=f"catalogue-page-{pages}.html")
        except FetchError as exc:
            failures.append({"url": url, "stage": "catalogue", "reason": exc.reason})
            break  # without this page we cannot know the next one
        links, url = parse_catalogue(page.html, page.url)
        found += [(link, page.url) for link in links]
    return found, pages


def extract(fetcher: Fetcher, url: str, source_page: str) -> dict:
    page = fetcher.get(url)
    raw = {"product_url": url, **parse_book(page.html), "source_page": source_page, "fetched_at": page.fetched_at}
    return {k: raw.get(k) for k in RAW_FIELDS}


def write_json(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), "utf-8")
    tmp.replace(path)  # atomic: a crash mid-write never leaves a half-written file


def write_csv(path: Path, books: list[dict]) -> None:
    cols = ["title", "price_gbp", "rating", "in_stock", "available_count", "product_url", "source_page",
            "fetched_at", "description"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for b in books:  # CSV is flat: newlines in descriptions are collapsed to spaces
            w.writerow({**b, "description": " ".join((b.get("description") or "").split())})


def run(with_broken_url: bool = False, with_csv: bool = False) -> dict:
    started, t0 = now_iso(), time.monotonic()
    fetcher = Fetcher(BASE / "cache")
    failures: list[dict] = []

    found, pages = discover(fetcher, failures)
    if with_broken_url:
        found.append((BROKEN_URL, START_URL))
    sources: dict[str, str] = {}
    for url, src in found:
        sources.setdefault(url, src)  # de-duplicate, remember the first catalogue page it appeared on
    print(f"catalogue_pages={pages} discovered={len(found)} unique_urls={len(sources)}")

    books: dict[str, dict] = {}  # keyed by canonical URL -> a rerun can never create duplicates
    errors: list[dict] = []
    for url, src in sources.items():
        try:  # each page on its own: one bad page is logged and skipped, never fatal
            raw = extract(fetcher, url, src)
        except FetchError as exc:
            failures.append({"url": url, "stage": "detail", "reason": exc.reason})
            print(f"  SKIP {url}: {exc.reason}")
            continue
        except Exception as exc:  # parser surprise on a malformed page
            failures.append({"url": url, "stage": "parse", "reason": f"{type(exc).__name__}: {exc}"})
            continue
        try:
            book = Book(**normalize(raw))
        except ValidationError as exc:
            errors.append({"product_url": url, "reason": exc.errors(include_url=False), "raw": raw})
            continue
        books[book.product_url] = book.model_dump(mode="json")

    OUT.mkdir(exist_ok=True)
    good = list(books.values())
    write_json(OUT / "books.json", good)
    write_json(OUT / "errors.json", errors)
    if with_csv:
        write_csv(OUT / "books.csv", good)

    report = {
        "started_at": started,
        "finished_at": now_iso(),
        "duration_s": round(time.monotonic() - t0, 2),
        "catalogue_pages": pages,
        "unique_urls": len(sources),
        "pages_fetched": fetcher.stats["pages_fetched"],
        "cache_hits": fetcher.stats["cache_hits"],
        "retries": fetcher.stats.get("retries", 0),
        "valid_records": len(good),
        "invalid_records": len(errors),
        "failed_pages": len(failures),
        "failures": failures,
    }
    write_json(OUT / "run-report.json", report)
    print(f"valid={len(good)} invalid={len(errors)} failed_pages={len(failures)} "
          f"fetched={report['pages_fetched']} cache_hits={report['cache_hits']} duration={report['duration_s']}s")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Polite scraper for books.toscrape.com (first 3 catalogue pages)")
    ap.add_argument("--with-broken-url", action="store_true", help="add one made-up book URL to prove failures are survived")
    ap.add_argument("--csv", action="store_true", help="also write output/books.csv")
    args = ap.parse_args()
    run(with_broken_url=args.with_broken_url, with_csv=args.csv)


if __name__ == "__main__":
    main()
