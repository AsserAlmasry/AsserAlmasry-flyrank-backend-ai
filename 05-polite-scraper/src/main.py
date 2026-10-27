"""The polite scraper. Run from this folder with:  python -m src.main"""
from pathlib import Path

from .fetch import Fetcher
from .parse import parse_catalogue

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
    unique = list(dict.fromkeys(url for url, _ in found))  # de-duplicate, keep order
    print(f"catalogue_pages={pages} discovered={len(found)} unique_urls={len(unique)} "
          f"(fetched={fetcher.stats['pages_fetched']} cache_hits={fetcher.stats['cache_hits']})")


if __name__ == "__main__":
    main()
