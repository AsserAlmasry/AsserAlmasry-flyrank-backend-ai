# My 10x Solution - Asser Almasry

**Project:** ShelfWatch, a competitor price & stock monitor
**Track:** Backend AI Engineering · FlyRank Internship capstone ("Your 10x Solution")
**Code:** <https://github.com/AsserAlmasry/AsserAlmasry-flyrank-backend-ai/tree/main/capstone-shelfwatch>

## 1. The problem

Small online booksellers have to price competitively, but the only way most of them can see a competitor's prices is to
open the competitor's website and check titles one by one. For a catalogue of 60 titles that is roughly an hour of
clicking, so in practice it happens once a week at best, and a price drop or a stock-out on the other side is noticed days
late, after the sales are already lost. These sellers are one- or two-person businesses with no data team and no budget
for paid price-tracking tools.

**The 10x claim:** what takes a person about 60 minutes, ShelfWatch does unattended every morning in about one minute
(67 seconds measured for 60 titles), and it remembers every change instead of relying on what someone happens to notice.

**Non-goal:** ShelfWatch does not change the seller's own prices. It reports what changed; a person decides what to do.

## 2. How I built it

ShelfWatch is a Python/FastAPI service backed by SQLite. A user signs up and logs in, then everything goes through a
token-protected API. A **scan** visits the competitor catalogue politely, at one request per second with an honest
user-agent, reads every title's price and stock, and compares it with what was stored last time. Every difference becomes a
row in a change log: new title, price up, price down, out of stock, back in stock. New titles get a category from an LLM,
chosen from a fixed list. Once a week a **PDF brief** summarises the biggest price moves, stock changes and the catalogue by
category. Scans run in the background (the API answers immediately with 202), and a scheduler starts a scan every morning and
a report every Monday with no one clicking anything.

I built it by reusing my own assignments, as the brief suggests: the scraper from BE-05, the auth pattern from BE-03, the
202-and-poll and cron patterns from BE-06, the PDF pipeline from A8 and the validated LLM call from A17.

### The concepts (7 core, no swaps)

| Concept | How ShelfWatch uses it |
|---|---|
| **API endpoints** | 14 endpoints with input validation and correct status codes (201, 202, 400, 401, 404, 409), consistent JSON errors, Swagger docs |
| **Database** | SQLite with seven tables, including price history (`snapshots`) and the change log (`changes`); it survives restarts |
| **Authentication** | sign-up/login, passwords hashed with scrypt and a random salt, JWT bearer tokens checked by one guard on every protected route |
| **Background + cron jobs** | scans run after a 202 and report their status; APScheduler runs a daily scan and a weekly report, never two at once |
| **Reporting (PDF)** | SQL aggregation → HTML → headless Chromium → PDF stored on disk and downloaded by link; one per day unless forced |
| **Caching** | dashboard stats cached for 5 minutes and cleared after every scan; scraped pages cached for 6 hours so the competitor's site isn't hit twice; LLM answers cached by a hash of the text |
| **LLM integration** | one narrow job (categorise a title from a list of 13), versioned prompt file, schema validation, one repair attempt, a cost log line per call, and an offline mode that needs no key |

No concepts were swapped. Web scraping is used as the data source, as a bonus on top of the seven.

### What I measured

- First scan: 60 titles in 67 seconds, 63 pages fetched, 0 failures.
- Second scan the same day: about 1 second, every page from the cache, 0 requests to the website, 20 changes detected.
- The test suite (13 tests) covers the risky parts: auth and expired tokens, change detection without duplicates, a broken
  page and a crashing scan, the cache being invalidated, the LLM repair-then-give-up rule, and one-report-per-day.

The demo target is books.toscrape.com, a practice site built to be scraped. Its prices never change, so for the demo a
`DEMO_DRIFT` switch simulates small, repeatable price and stock moves. It is clearly labelled and off for real use.

## 3. How to run it

```bash
git clone https://github.com/AsserAlmasry/AsserAlmasry-flyrank-backend-ai.git
cd AsserAlmasry-flyrank-backend-ai/capstone-shelfwatch
cp .env.example .env                 # set JWT_SECRET to a long random string
pip install -r requirements.txt && playwright install chromium
uvicorn app.main:app --port 8000     # then open http://localhost:8000/docs
```

Demo path: sign up → log in → **Authorize** in Swagger → `POST /scans` → poll `GET /scans/1` → `POST /scans` again (with
`DEMO_DRIFT=1`) → `GET /changes` → `POST /reports` → download the PDF. Everything is free and needs no API keys; to use a real
LLM, set `LLM_STUB=0` and point `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` at Ollama, OpenRouter or any OpenAI-compatible
provider.
