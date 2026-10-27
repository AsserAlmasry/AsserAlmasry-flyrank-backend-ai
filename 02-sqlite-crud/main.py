from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from db import TaskRepository, init_db

app = FastAPI(title="Task API (SQLite)", version="2.0")
init_db()
repo = TaskRepository()


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body") or "body"
    return JSONResponse(status_code=400, content={"error": f"Invalid '{field}': {first['msg']}"})


def bad_request(msg: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": msg})


def not_found(task_id: int) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": f"Task {task_id} not found"})


@app.get("/")
def root():
    return {"name": "Task API", "version": "2.0", "storage": "sqlite", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks():
    return repo.list()


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    task = repo.get(task_id)
    return task if task else not_found(task_id)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1)


@app.post("/tasks", status_code=201)
def create_task(body: TaskCreate):
    if not body.title.strip():
        return bad_request("title must not be empty")
    return repo.create(body.title.strip())


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    done: bool | None = None


@app.put("/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate):
    if body.title is None and body.done is None:
        return bad_request("send at least one of: title, done")
    if body.title is not None and not body.title.strip():
        return bad_request("title must not be empty")
    task = repo.update(task_id, body.title.strip() if body.title else None, body.done)
    return task if task else not_found(task_id)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    if not repo.delete(task_id):
        return not_found(task_id)
    return Response(status_code=204)
