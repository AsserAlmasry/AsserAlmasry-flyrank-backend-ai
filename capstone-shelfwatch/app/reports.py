"""Weekly PDF brief: SQL aggregation -> HTML template -> headless Chromium -> file on disk, served by link."""
import threading
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

from . import config, db

_lock = threading.Lock()  # a double-clicked "generate" or a cron run overlapping a click makes one file, not two

LABELS = {"new": "New title", "price_up": "Price up", "price_down": "Price down",
          "out_of_stock": "Out of stock", "back_in_stock": "Back in stock"}


def report_data(days: int = 7) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    with db.tx() as conn:
        totals = dict(conn.execute("""SELECT COUNT(*) AS title_count, ROUND(AVG(price), 2) AS avg_price,
                                             SUM(CASE WHEN in_stock THEN 0 ELSE 1 END) AS out_of_stock FROM books""").fetchone())
        by_kind = {r["kind"]: r["n"] for r in conn.execute(
            "SELECT kind, COUNT(*) AS n FROM changes WHERE detected_at >= ? GROUP BY kind", (since,))}
        moves = [dict(r) for r in conn.execute(
            """SELECT b.title, c.kind, CAST(c.old_value AS REAL) AS old_price, CAST(c.new_value AS REAL) AS new_price,
                      ROUND((CAST(c.new_value AS REAL) - CAST(c.old_value AS REAL)) / CAST(c.old_value AS REAL) * 100, 1) AS pct
               FROM changes c JOIN books b ON b.id = c.book_id
               WHERE c.kind IN ('price_up','price_down') AND c.detected_at >= ?
               ORDER BY ABS(CAST(c.new_value AS REAL) - CAST(c.old_value AS REAL)) DESC LIMIT 10""", (since,))]
        stock = [dict(r) for r in conn.execute(
            """SELECT b.title, c.kind, c.detected_at FROM changes c JOIN books b ON b.id = c.book_id
               WHERE c.kind IN ('out_of_stock','back_in_stock') AND c.detected_at >= ? ORDER BY c.detected_at DESC""", (since,))]
        categories = [dict(r) for r in conn.execute(
            """SELECT COALESCE(e.category, 'not categorised') AS category, COUNT(*) AS titles, ROUND(AVG(b.price), 2) AS avg_price
               FROM books b LEFT JOIN enrichments e ON e.book_id = b.id GROUP BY 1 ORDER BY titles DESC""")]
        titles = [dict(r) for r in conn.execute(
            """SELECT b.title, b.price, b.in_stock, COALESCE(e.category, '') AS category FROM books b
               LEFT JOIN enrichments e ON e.book_id = b.id ORDER BY b.title COLLATE NOCASE""")]
    return {"days": days, **totals, "changes_by_kind": by_kind, "biggest_moves": moves, "stock_changes": stock,
            "categories": categories, "titles": titles}


CSS = """
@page { size: A4; margin: 16mm 13mm 18mm; }
* { box-sizing: border-box; }
body { font-family: Helvetica, Arial, sans-serif; color: #18202e; font-size: 10.5px; margin: 0; }
h1 { color: #0e7490; font-size: 22px; margin: 0; } .sub { color: #5b6475; margin: 2px 0 14px; }
h2 { color: #0e7490; font-size: 13px; margin: 18px 0 6px; break-after: avoid; }
.kpis { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; } .kpi { min-width: 0; border: 1px solid #d6dde6; border-radius: 8px; padding: 10px; background: #f5fafb; }
.kpi .v { font-size: 22px; font-weight: 700; } .kpi .l { font-size: 8.5px; color: #5b6475; text-transform: uppercase; letter-spacing: .05em; }
table { width: 100%; border-collapse: collapse; } th, td { text-align: left; padding: 5px 7px; border-bottom: 1px solid #e3e8ef; }
th { background: #0e7490; color: #fff; font-size: 9px; text-transform: uppercase; } td.n, th.n { text-align: right; white-space: nowrap; }
thead { display: table-header-group; } tr { break-inside: avoid; } .up { color: #b91c1c; } .down { color: #15803d; }
.empty { color: #8a93a3; font-style: italic; } .long { break-before: page; }
"""

FOOTER = ("<div style='font-size:8px;color:#8a93a3;width:100%;padding:0 13mm;display:flex;justify-content:space-between'>"
          "<span>ShelfWatch weekly brief · source: books.toscrape.com</span>"
          "<span>Page <span class='pageNumber'></span> of <span class='totalPages'></span></span></div>")


def build_html(d: dict, today: date) -> str:
    gbp = lambda v: f"£{v:,.2f}" if v is not None else "–"  # noqa: E731
    k = d["changes_by_kind"]
    moves = "".join(
        f"<tr><td>{escape(m['title'])}</td><td class='n'>{gbp(m['old_price'])}</td><td class='n'>{gbp(m['new_price'])}</td>"
        f"<td class='n {'up' if m['pct'] > 0 else 'down'}'>{m['pct']:+.1f}%</td></tr>" for m in d["biggest_moves"]
    ) or "<tr><td colspan='4' class='empty'>No price changes this week.</td></tr>"
    stock = "".join(f"<tr><td>{escape(s['title'])}</td><td>{LABELS[s['kind']]}</td><td>{s['detected_at'][:10]}</td></tr>"
                    for s in d["stock_changes"]) or "<tr><td colspan='3' class='empty'>No stock changes this week.</td></tr>"
    cats = "".join(f"<tr><td>{escape(c['category'])}</td><td class='n'>{c['titles']}</td><td class='n'>{gbp(c['avg_price'])}</td></tr>"
                   for c in d["categories"])
    titles = "".join(f"<tr><td>{escape(t['title'])}</td><td>{escape(t['category'])}</td><td class='n'>{gbp(t['price'])}</td>"
                     f"<td>{'yes' if t['in_stock'] else '<b class=up>no</b>'}</td></tr>" for t in d["titles"])
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<h1>ShelfWatch weekly brief</h1><div class="sub">{today.strftime('%A %d %B %Y')} · last {d['days']} days</div>
<div class="kpis">
 <div class="kpi"><div class="l">Titles tracked</div><div class="v">{d['title_count']}</div></div>
 <div class="kpi"><div class="l">Average price</div><div class="v">{gbp(d['avg_price'])}</div></div>
 <div class="kpi"><div class="l">Price moves</div><div class="v">{k.get('price_up', 0) + k.get('price_down', 0)}</div></div>
 <div class="kpi"><div class="l">Out of stock now</div><div class="v">{d['out_of_stock'] or 0}</div></div>
 <div class="kpi"><div class="l">New titles</div><div class="v">{k.get('new', 0)}</div></div>
</div>
<h2>Biggest price moves</h2><table><thead><tr><th>Title</th><th class="n">Was</th><th class="n">Now</th><th class="n">Change</th></tr></thead><tbody>{moves}</tbody></table>
<h2>Stock changes</h2><table><thead><tr><th>Title</th><th>Change</th><th>Seen</th></tr></thead><tbody>{stock}</tbody></table>
<h2>Catalogue by AI category</h2><table><thead><tr><th>Category</th><th class="n">Titles</th><th class="n">Avg price</th></tr></thead><tbody>{cats}</tbody></table>
<h2 class="long">All tracked titles</h2><table><thead><tr><th>Title</th><th>Category</th><th class="n">Price</th><th>In stock</th></tr></thead><tbody>{titles}</tbody></table>
</body></html>"""


def render_pdf(html: str, path: Path) -> None:
    from playwright.sync_api import sync_playwright
    path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.pdf(path=str(path), format="A4", print_background=True, display_header_footer=True,
                     header_template="<span></span>", footer_template=FOOTER,
                     margin={"top": "16mm", "bottom": "18mm", "left": "13mm", "right": "13mm"})
        finally:
            browser.close()


def generate(triggered_by: str, force: bool = False) -> tuple[dict, bool]:
    """Returns (report_row, created). One report per day unless force=True."""
    with _lock:
        today = date.today().isoformat()
        if not force:
            with db.tx() as conn:
                row = conn.execute("SELECT * FROM reports WHERE report_date=? ORDER BY id DESC LIMIT 1", (today,)).fetchone()
            if row:
                return dict(row), False
        with db.tx() as conn:
            rid = conn.execute("INSERT INTO reports (path, report_date, created_at, triggered_by) VALUES ('', ?, ?, ?)",
                               (today, db.now(), triggered_by)).lastrowid
        path = config.REPORTS_DIR / f"shelfwatch-brief-{today}-{rid}.pdf"
        try:
            render_pdf(build_html(report_data(), date.today()), path)
        except Exception:
            with db.tx() as conn:
                conn.execute("DELETE FROM reports WHERE id=?", (rid,))
            raise
        with db.tx() as conn:
            conn.execute("UPDATE reports SET path=? WHERE id=?", (path.name, rid))
            return dict(conn.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()), True
