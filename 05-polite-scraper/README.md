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
