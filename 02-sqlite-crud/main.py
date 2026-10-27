from fastapi import FastAPI

from db import init_db

app = FastAPI(title="Task API (SQLite)", version="2.0")
init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
