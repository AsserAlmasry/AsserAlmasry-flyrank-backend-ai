from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import db


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="ShelfWatch", version="0.1", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/books")
def list_books():
    with db.tx() as conn:
        return [dict(r) for r in conn.execute("SELECT id, title, price, in_stock FROM books ORDER BY title")]
