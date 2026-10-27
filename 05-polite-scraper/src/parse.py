"""HTML extraction. Pure functions: HTML string in, Python values out (easy to test with fixtures)."""
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def parse_catalogue(html: str, page_url: str) -> tuple[list[str], str | None]:
    """Return (absolute book URLs on this page, absolute URL of the next page or None)."""
    soup = BeautifulSoup(html, "html.parser")
    links = [urljoin(page_url, a["href"]) for a in soup.select("article.product_pod h3 a[href]")]
    nxt = soup.select_one("ul.pager li.next a[href]")
    return links, (urljoin(page_url, nxt["href"]) if nxt else None)


def _text(node) -> str | None:
    return " ".join(node.get_text(" ", strip=True).split()) if node else None


def parse_book(html: str) -> dict:
    """Extract the raw (uncleaned) fields from a book page. Selectors aim at the product area only."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("article.product_page div.product_main")
    if main is None:
        raise ValueError("product area (article.product_page div.product_main) not found")
    rating = main.select_one("p.star-rating")
    rating_text = next((c for c in rating.get("class", []) if c != "star-rating"), None) if rating else None
    heading = soup.select_one("article.product_page #product_description")
    desc_node = heading.find_next_sibling("p") if heading else None
    return {
        "title": _text(main.select_one("h1")),
        "price_text": _text(main.select_one("p.price_color")),
        "availability_text": _text(main.select_one("p.availability")),
        "rating_text": rating_text,
        "description": _text(desc_node) or None,  # missing description -> None, never invented text
    }
