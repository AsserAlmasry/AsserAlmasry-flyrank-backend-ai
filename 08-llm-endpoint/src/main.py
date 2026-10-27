"""Run:  uvicorn src.main:app --reload --port 8000"""
import logging

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

load_dotenv()
# Cost log lines go to stdout as structured JSON (twelve-factor: let the environment route logs).
logging.basicConfig(level=logging.INFO, format="%(message)s")

from .routes.enrich import router  # noqa: E402  (after load_dotenv so settings see .env)

app = FastAPI(title="Book Enrichment API", version="1.0",
              description="POST a scraped book, get back a category, a one-line summary and quality flags.")


@app.exception_handler(RequestValidationError)
async def bad_input(_: Request, exc: RequestValidationError):
    # 400 naming the offending field, BEFORE any model call is made (every rejected request is a call not paid for).
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body") or "body"
    return JSONResponse(status_code=400, content={"error": "invalid_input", "field": field, "message": first["msg"]})


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(router)
