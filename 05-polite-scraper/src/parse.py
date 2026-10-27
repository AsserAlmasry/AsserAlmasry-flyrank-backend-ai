"""HTML extraction. Pure functions: HTML string in, Python values out (easy to test with fixtures)."""
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def parse_catalogue(html: str, page_url: str) -> tuple[list[str], str | None]:
    """Return (absolute book URLs on this page, absolute URL of the next page or None)."""
    soup = BeautifulSoup(html, "html.parser")
    links = [urljoin(page_url, a["href"]) for a in soup.select("article.product_pod h3 a[href]")]
    nxt = soup.select_one("ul.pager li.next a[href]")
    return links, (urljoin(page_url, nxt["href"]) if nxt else None)
