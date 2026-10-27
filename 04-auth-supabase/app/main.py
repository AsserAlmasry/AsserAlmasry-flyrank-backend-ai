from fastapi import FastAPI

from .supabase_client import get_settings, new_client

app = FastAPI(title="Auth API (Supabase)", version="1.0")


@app.on_event("startup")
def check_supabase() -> None:
    url, _ = get_settings()
    new_client()  # fails fast if the URL/key are malformed
    print(f"Server running and connected to Supabase ({url})")


@app.get("/health")
def health():
    return {"status": "ok"}
