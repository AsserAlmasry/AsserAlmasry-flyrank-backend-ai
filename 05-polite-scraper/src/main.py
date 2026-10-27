"""The polite scraper. Run from this folder with:  python -m src.main"""
from pathlib import Path

from .fetch import Fetcher

BASE = Path(__file__).resolve().parent.parent
START_URL = "https://books.toscrape.com/catalogue/page-1.html"


def main() -> None:
    fetcher = Fetcher(BASE / "cache")
    page = fetcher.get(START_URL, cache_name="catalogue-page-1.html")
    label = "CACHE HIT" if page.from_cache else "FETCH"
    print(f"{label} {START_URL} size={len(page.html.encode())} bytes")


if __name__ == "__main__":
    main()
