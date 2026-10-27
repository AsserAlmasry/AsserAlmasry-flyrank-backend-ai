"""Stage 2: boring SQL is 80% of reporting. Rows in, a handful of numbers out."""
import json

from db import connect

TOTALS_SQL = "SELECT COUNT(*) AS total_books, ROUND(AVG(price), 2) AS average_price FROM books"

TOP5_SQL = """
SELECT title, price, rating
FROM books
ORDER BY price DESC, title
LIMIT 5
"""

PER_RATING_SQL = """
SELECT rating, COUNT(*) AS books, ROUND(AVG(price), 2) AS average_price
FROM books
GROUP BY rating
ORDER BY rating DESC
"""

ALL_BOOKS_SQL = "SELECT title, price, rating FROM books ORDER BY title COLLATE NOCASE"


def get_report_data() -> dict:
    with connect() as conn:
        totals = dict(conn.execute(TOTALS_SQL).fetchone())
        top5 = [dict(r) for r in conn.execute(TOP5_SQL)]
        per_rating = [dict(r) for r in conn.execute(PER_RATING_SQL)]
        all_books = [dict(r) for r in conn.execute(ALL_BOOKS_SQL)]
    return {**totals, "top_5_most_expensive": top5, "books_per_rating": per_rating, "all_books": all_books}


if __name__ == "__main__":
    data = get_report_data()
    data["all_books"] = f"<{len(data['all_books'])} rows, used for the long table>"
    print(json.dumps(data, indent=2, ensure_ascii=False))
