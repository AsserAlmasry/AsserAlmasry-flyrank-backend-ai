"""Stage 3: you don't draw a PDF. You write a web page and ask a (headless) browser to print it."""
import asyncio
from datetime import date
from html import escape
from pathlib import Path

from playwright.async_api import async_playwright

from report_data import get_report_data

STARS = {n: "★" * n + "☆" * (5 - n) for n in range(1, 6)}

CSS = """
@page { size: A4; margin: 18mm 14mm 20mm; }
* { box-sizing: border-box; }
body { font-family: "Helvetica Neue", Arial, sans-serif; color: #1d2433; font-size: 11px; margin: 0; }
header { border-bottom: 3px solid #0f766e; padding-bottom: 10px; margin-bottom: 18px; }
h1 { font-size: 24px; margin: 0 0 4px; color: #0f766e; }
.sub { color: #5b6475; font-size: 12px; }
h2 { font-size: 14px; margin: 22px 0 8px; color: #0f766e; break-after: avoid; }
.kpis { display: flex; gap: 12px; }
.kpi { flex: 1; border: 1px solid #d6dde6; border-radius: 8px; padding: 12px 14px; background: #f6faf9; }
.kpi .v { font-size: 26px; font-weight: 700; }
.kpi .l { color: #5b6475; text-transform: uppercase; letter-spacing: .06em; font-size: 9px; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #e3e8ef; vertical-align: top; }
th { background: #0f766e; color: #fff; font-weight: 600; font-size: 10px; text-transform: uppercase; letter-spacing: .04em; }
td.num, th.num { text-align: right; white-space: nowrap; }
tbody tr:nth-child(even) td { background: #f7f9fb; }
.stars { color: #d97706; letter-spacing: 1px; white-space: nowrap; }
/* The page-break fix: never slice a row, and repeat the header row on every page. */
thead { display: table-header-group; }
tr { break-inside: avoid; page-break-inside: avoid; }
.long { break-before: page; }
"""

FOOTER = """<div style="font-size:8px;color:#8a93a3;width:100%;padding:0 14mm;display:flex;justify-content:space-between;">
<span>Bookstore report · source: books.toscrape.com (scraped in BE-05)</span>
<span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>"""


def build_html(data: dict, today: date) -> str:
    def money(v: float) -> str:
        return f"£{v:,.2f}"

    top5 = "".join(f"<tr><td>{i}</td><td>{escape(b['title'])}</td><td class='num'>{money(b['price'])}</td>"
                   f"<td class='stars'>{STARS[b['rating']]}</td></tr>"
                   for i, b in enumerate(data["top_5_most_expensive"], 1))
    per_rating = "".join(f"<tr><td class='stars'>{STARS[r['rating']]}</td><td class='num'>{r['books']}</td>"
                         f"<td class='num'>{money(r['average_price'])}</td></tr>" for r in data["books_per_rating"])
    all_rows = "".join(f"<tr><td class='num'>{i}</td><td>{escape(b['title'])}</td><td class='num'>{money(b['price'])}</td>"
                       f"<td class='stars'>{STARS[b['rating']]}</td></tr>" for i, b in enumerate(data["all_books"], 1))
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<header><h1>Bookstore report</h1><div class="sub">Generated {today.strftime('%A %d %B %Y')} · first 3 catalogue pages of Books to Scrape</div></header>
<div class="kpis">
  <div class="kpi"><div class="l">Total books</div><div class="v">{data['total_books']}</div></div>
  <div class="kpi"><div class="l">Average price</div><div class="v">{money(data['average_price'])}</div></div>
</div>
<h2>Top 5 most expensive books</h2>
<table><thead><tr><th>#</th><th>Title</th><th class="num">Price</th><th>Rating</th></tr></thead><tbody>{top5}</tbody></table>
<h2>Books per star rating</h2>
<table><thead><tr><th>Rating</th><th class="num">Books</th><th class="num">Average price</th></tr></thead><tbody>{per_rating}</tbody></table>
<h2 class="long">All books ({len(data['all_books'])})</h2>
<table><thead><tr><th class="num">#</th><th>Title</th><th class="num">Price</th><th>Rating</th></tr></thead><tbody>{all_rows}</tbody></table>
</body></html>"""


async def render_pdf(path: Path, data: dict | None = None, today: date | None = None) -> Path:
    html = build_html(data or get_report_data(), today or date.today())
    path.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content(html, wait_until="load")
            await page.pdf(path=str(path), format="A4", print_background=True, display_header_footer=True,
                           header_template="<span></span>", footer_template=FOOTER,
                           margin={"top": "18mm", "bottom": "20mm", "left": "14mm", "right": "14mm"})
        finally:
            await browser.close()
    return path


if __name__ == "__main__":
    out = asyncio.run(render_pdf(Path(__file__).parent / "reports" / "test.pdf"))
    print(f"wrote {out}")
