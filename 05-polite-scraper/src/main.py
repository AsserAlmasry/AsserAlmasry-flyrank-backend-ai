"""The polite scraper. Run from this folder with:  python -m src.main"""
import json
from pathlib import Path

from pydantic import ValidationError

from .fetch import Fetcher
from .models import Book, normalize
from .parse import parse_book, parse_catalogue

BASE = Path(__file__).resolve().parent.parent
START_URL = "https://books.toscrape.com/catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3


def discover(fetcher: Fetcher) -> tuple[list[tuple[str, str]], int]:
    """Follow the site's own "next" links for 3 pages. Returns ([(book_url, source_page)], pages_seen)."""
    found, url, pages = [], START_URL, 0
    while url and pages < MAX_CATALOGUE_PAGES:
        pages += 1
        page = fetcher.get(url, cache_name=f"catalogue-page-{pages}.html")
        links, url = parse_catalogue(page.html, page.url)
        found += [(link, page.url) for link in links]
    return found, pages


def main() -> None:
    fetcher = Fetcher(BASE / "cache")
    found, pages = discover(fetcher)
    sources = dict(reversed(found))  # url -> first catalogue page it appeared on
    unique = list(dict.fromkeys(url for url, _ in found))
    print(f"catalogue_pages={pages} discovered={len(found)} unique_urls={len(unique)}")

    raw_records = []
    for url in unique:
        page = fetcher.get(url)
        raw = {"title": None, "product_url": url}
        raw.update(parse_book(page.html))
        raw.update(source_page=sources[url], fetched_at=page.fetched_at)
        raw_records.append({k: raw[k] for k in ("title", "product_url", "price_text", "availability_text",
                                                  "rating_text", "description", "source_page", "fetched_at")})
    print(f"detail_pages={len(raw_records)}")

    books: dict[str, dict] = {}  # keyed by canonical URL -> a rerun can never create duplicates
    errors = []
    for raw in raw_records:
        try:
            book = Book(**normalize(raw))
        except ValidationError as exc:
            errors.append({"product_url": raw.get("product_url"), "reason": exc.errors(include_url=False),
                           "raw": raw})
            continue
        books[book.product_url] = book.model_dump(mode="json")

    out = BASE / "output"
    out.mkdir(exist_ok=True)
    write_json(out / "books.json", list(books.values()))
    write_json(out / "errors.json", errors)
    print(f"valid={len(books)} invalid={len(errors)} -> output/books.json")


def write_json(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), "utf-8")
    tmp.replace(path)  # atomic: a crash mid-write never leaves a half-written books.json


if __name__ == "__main__":
    main()
