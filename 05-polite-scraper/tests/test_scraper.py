"""Fixture tests: no network to the real site. Run with:  pytest -q"""
import http.server
import threading
from pathlib import Path

import pytest
from pydantic import ValidationError

from src import fetch as fetch_module
from src.fetch import Fetcher, FetchError
from src.models import Book, normalize, parse_price
from src.parse import parse_book, parse_catalogue

FIX = Path(__file__).parent / "fixtures"
PAGE_URL = "https://books.toscrape.com/catalogue/page-1.html"


@pytest.mark.parametrize("text,expected", [("£51.77", 51.77), ("£ 1,234.50", 1234.5), ("Â£13.99", 13.99),
                                           ("free!", None), (None, None)])
def test_price_normalization(text, expected):
    assert parse_price(text) == expected


def test_relative_links_become_absolute_and_next_is_followed():
    links, nxt = parse_catalogue((FIX / "catalogue_with_duplicate.html").read_text(), PAGE_URL)
    assert links[0] == "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    assert all(link.startswith("https://") for link in links)
    assert nxt == "https://books.toscrape.com/catalogue/page-2.html"


def test_duplicate_urls_collapse_to_one():
    links, _ = parse_catalogue((FIX / "catalogue_with_duplicate.html").read_text(), PAGE_URL)
    assert len(links) == 3 and len(dict.fromkeys(links)) == 2


def test_missing_description_is_none_and_whitespace_is_cleaned():
    raw = parse_book((FIX / "book_no_description.html").read_text())
    assert raw == {"title": "The Book With No Blurb", "price_text": "£12.50",
                   "availability_text": "In stock (3 available)", "rating_text": "Four", "description": None}


def test_malformed_page_raises_instead_of_inventing_data():
    with pytest.raises(ValueError):
        parse_book((FIX / "malformed.html").read_text())


def test_schema_rejects_bad_records():
    good = normalize({"title": "X", "product_url": "https://books.toscrape.com/catalogue/x_1/index.html",
                      "price_text": "£1.00", "availability_text": "In stock (1 available)", "rating_text": "One",
                      "description": None, "source_page": PAGE_URL, "fetched_at": "2026-10-27T09:00:00Z"})
    assert Book(**good).price_gbp == 1.0
    for bad in ({"price_gbp": None}, {"product_url": "http://evil.example/x"}, {"rating_text": "Six", "rating": None}):
        with pytest.raises(ValidationError):
            Book(**{**good, **bad})


# --------------------------------------------------------------- retry rules (local server only)

class Handler(http.server.BaseHTTPRequestHandler):
    hits: dict = {}

    def do_GET(self):
        Handler.hits[self.path] = Handler.hits.get(self.path, 0) + 1
        if self.path == "/flaky" and Handler.hits[self.path] == 1:
            self.send_response(503); self.end_headers(); return
        code = {"/missing": 404, "/forbidden": 403, "/down": 500}.get(self.path, 200)
        self.send_response(code); self.end_headers()
        self.wfile.write(b"<html>ok</html>")

    def log_message(self, *args):
        pass


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(fetch_module, "MIN_DELAY_S", 0)
    monkeypatch.setattr(fetch_module, "RETRY_WAIT_S", 0)
    Handler.hits = {}
    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_404_and_403_are_never_retried(server, tmp_path):
    f = Fetcher(tmp_path)
    for path in ("/missing", "/forbidden"):
        with pytest.raises(FetchError):
            f.get(server + path)
        assert Handler.hits[path] == 1


def test_5xx_is_retried_exactly_once(server, tmp_path):
    f = Fetcher(tmp_path)
    assert f.get(server + "/flaky").html == "<html>ok</html>"   # 503, then 200
    assert Handler.hits["/flaky"] == 2
    with pytest.raises(FetchError):
        f.get(server + "/down")                                     # 500, 500 -> give up
    assert Handler.hits["/down"] == 2


def test_second_get_is_a_cache_hit(server, tmp_path):
    f = Fetcher(tmp_path)
    assert f.get(server + "/ok").from_cache is False
    assert f.get(server + "/ok").from_cache is True
    assert Handler.hits["/ok"] == 1 and f.stats == {"pages_fetched": 1, "cache_hits": 1}
