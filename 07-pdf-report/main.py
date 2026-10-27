from fastapi import FastAPI

app = FastAPI(title="Bookstore PDF Reports")


@app.get("/health")
def health():
    return {"status": "ok"}
