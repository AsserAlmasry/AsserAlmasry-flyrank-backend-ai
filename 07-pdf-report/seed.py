"""Seed report.db with the 60 books scraped in BE-05 (Option B: the bookstore).

Safe to run twice: it deletes all rows first, so you always end with exactly one clean copy.
Usage:  python seed.py
"""
import json

from db import BASE, connect

SOURCE = BASE / "data" / "books.json"  # copied from ../05-polite-scraper/output/books.json


def seed() -> int:
    books = json.loads(SOURCE.read_text("utf-8"))
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS books (
                            id     INTEGER PRIMARY KEY AUTOINCREMENT,
                            title  TEXT    NOT NULL,
                            price  REAL    NOT NULL,
                            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                            url    TEXT    NOT NULL UNIQUE
                        )""")
        conn.execute("DELETE FROM books")  # start clean -> running twice never doubles the rows
        conn.executemany("INSERT INTO books (title, price, rating, url) VALUES (?, ?, ?, ?)",
                         [(b["title"], b["price_gbp"], b["rating"], b["product_url"]) for b in books])
        (count,) = conn.execute("SELECT COUNT(*) FROM books").fetchone()
    return count


if __name__ == "__main__":
    print(f"SELECT COUNT(*) FROM books -> {seed()}")
