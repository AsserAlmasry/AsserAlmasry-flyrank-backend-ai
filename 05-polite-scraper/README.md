# BE-05 — The polite scraper

## Target classification

| Question | Answer |
|---|---|
| Which site? | [Books to Scrape](https://books.toscrape.com), part of [toscrape.com](https://toscrape.com) |
| Why is it OK? | toscrape.com describes it as *"a fictional bookstore that desperately wants to be scraped. It's a safe place for beginners learning web scraping"*. It is a sandbox built for exactly this. |
| robots.txt | Requested `https://books.toscrape.com/robots.txt` once on 2026-10-27: **HTTP 404, no robots file found.** A missing file is not permission; the sandbox statement above is. |
| How much? | Only the **first 3 catalogue pages** (`page-1.html` → `page-3.html`) and the **60 book pages** they link to. |
| What data? | Per book: title, product URL, price, availability, star rating, description, plus provenance (source page + fetch time). No personal data. |
| Why appropriate? | It's a public practice site, the data is fictional, the volume is tiny (63 pages, fetched once and then cached), and every request identifies me. |

**I will not reuse this code on another site without checking its rules and terms first.**

## What it does

A small, polite scraping pipeline: it downloads the first 3 catalogue pages of Books to Scrape, visits all 60 book pages,
turns the messy HTML into clean, schema-checked JSON, survives a broken page without crashing, and ends every run with a
report.

```
fetch (polite + cached) -> extract (BeautifulSoup) -> normalize -> validate (Pydantic) -> store (books.json) -> report
```

## Run it (one command)

Lane: **Python 3.10+** with `requests`, `beautifulsoup4`, `pydantic`.

```bash
cd 05-polite-scraper
pip install -r requirements.txt && python -m src.main
```

Output appears in `output/`: `books.json` (60 records), `errors.json` (records that failed validation), and
`run-report.json`. The first run takes about a minute because it waits between requests. Later runs read from `cache/`
and take under a second.

Options: `--with-broken-url` (Stage 5 proof, adds one made-up book URL) · `--csv` (also writes `output/books.csv`).
Tests: `pytest -q` (13 tests, no network to the real site).

## The record schema

Defined once in [`src/models.py`](src/models.py) (`class Book`). Raw text and clean values live side by side:

| Field | Type | Notes |
|---|---|---|
| `product_url` | str, required | canonical **absolute** URL, must match `https://books.toscrape.com/catalogue/.../index.html`. The record's identity. |
| `source_page` | str, required | catalogue page the link was found on (provenance) |
| `fetched_at` | datetime, required | when the page was actually fetched from the site (kept when later read from cache) |
| `title` | str, required | non-empty |
| `price_text` → `price_gbp` | str → float | `"£51.77"` → `51.77`, must be > 0 |
| `availability_text` → `in_stock`, `available_count` | str → bool, int \| null | `"In stock (22 available)"` → `true`, `22` |
| `rating_text` → `rating` | `One`…`Five` → int 1–5 | |
| `description` | str \| **null** | optional. A missing description is stored as `null`, never invented |

Unknown extra fields are rejected (`extra="forbid"`). A record that fails any rule goes to `errors.json` with the reason and
the raw values. It never reaches `books.json`.

## Politeness rules

| Rule | How |
|---|---|
| Say who I am | `User-Agent: FlyRankInternshipA9/1.0 (+https://github.com/AsserAlmasry/flyrank-backend-ai)` |
| Go slowly | at least **1 s** between real requests (the brief asks for ≥ 0.5 s). Cache hits never wait. |
| Never hang | **10 s** timeout on every request |
| Check the answer | anything except `200` is a failed fetch, not HTML to parse |
| Ask once | every page is saved to `cache/` with a `.meta.json` (URL, status, fetched_at). Development reads the cache. |
| Retry wisely | **one** retry after 3 s, only on timeout / network error / `5xx`. **Never** on `404` or `403`. |
| Stay in scope | exactly 3 catalogue pages, found by following the site's own "next" link (no hard-coded book URLs) |

`cache/` is in `.gitignore`. Only code and one sample output are committed.

## Proof: a run with one broken page

`python -m src.main --with-broken-url` adds a made-up book URL on purpose. The run finishes, the 60 good records survive, the
404 is **not** retried, and the report shows it:

```json
{
  "started_at": "2026-10-27T09:27:32Z",
  "finished_at": "2026-10-27T09:27:33Z",
  "duration_s": 0.94,
  "catalogue_pages": 3,
  "unique_urls": 61,
  "pages_fetched": 1,
  "cache_hits": 63,
  "retries": 0,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 1,
  "failures": [
    {
      "url": "https://books.toscrape.com/catalogue/this-book-does-not-exist_99999/index.html",
      "stage": "detail",
      "reason": "HTTP 404"
    }
  ]
}
```

Idempotency: running the scraper again still gives exactly **60** records. `books.json` is rebuilt from a dict keyed by
`product_url` and written atomically (temp file + rename), so a rerun replaces records instead of appending duplicates.

## Why no browser was needed

The book data is already in the HTML the server sends (the site needs no JavaScript), so a plain HTTP request gets
everything. A headless browser would only add seconds and hundreds of MB of memory per page.

## One honest limitation

The scraper finds the 3 catalogue pages by following "next" links, so if page 1 fails to load the run stops discovering
(it can't know page 2's address). It reports this as a failed catalogue page instead of crashing, but a smarter version
could fall back to the known URL pattern `page-N.html`. Also, the cache never expires: to refresh prices you delete
`cache/`.

## Ethics note

Use an official API whenever one exists: it is faster and it is what the site owner wants you to use. Never get around
logins, paywalls, CAPTCHAs or blocks; if a site says no (403, robots rules, terms), the answer is no. Collect only the fields
you actually need, identify yourself, and go slowly enough that the site owner would never notice you.

## Optional extras done

- **Fixture tests** ([`tests/test_scraper.py`](tests/test_scraper.py)): price normalization, relative → absolute URLs,
  missing description + extra whitespace, duplicate URLs, a malformed page, schema rejections, and the retry rules
  (404/403 never retried, 5xx retried exactly once, second fetch is a cache hit) against a local test server.
- **CSV export** (`--csv`): `output/books.csv`. Flattened: the multi-line `description` is collapsed to a single line, and
  nested/raw fields like `price_text` are dropped in favour of the clean values.
