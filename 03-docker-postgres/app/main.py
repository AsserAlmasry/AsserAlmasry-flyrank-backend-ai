import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from dotenv import load_dotenv

from .repository import InMemoryTaskRepository
from .service import TaskService, ValidationError

load_dotenv()  # reads .env when running outside Docker; compose passes the same vars in


def build_repository():
    """The ONLY place that knows which storage we use."""
    if os.getenv("STORAGE", "postgres") == "memory":
        return InMemoryTaskRepository()
    from .postgres_repository import PostgresTaskRepository
    return PostgresTaskRepository(os.environ["DATABASE_URL"])


repo = build_repository()
app = FastAPI(title="Task API (Postgres)", version="3.0")
service = TaskService(repo)


class TaskCreate(BaseModel):
    title: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None


@app.exception_handler(RequestValidationError)
async def request_validation_error(_: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body") or "body"
    return JSONResponse(status_code=400, content={"error": f"Invalid '{field}': {first['msg']}"})


@app.exception_handler(ValidationError)
async def service_validation_error(_: Request, exc: ValidationError):
    return JSONResponse(status_code=400, content={"error": str(exc)})


def not_found(task_id: int) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": f"Task {task_id} not found"})


@app.get("/health")
def health():
    status = {"status": "ok", "storage": type(repo).__name__}
    redis_url = os.getenv("REDIS_URL")
    if redis_url:  # stretch: prove the app can reach Redis
        import redis
        try:
            status["redis"] = "PONG" if redis.Redis.from_url(redis_url, socket_timeout=2).ping() else "no reply"
        except redis.RedisError as exc:
            status["redis"] = f"error: {exc}"
    return status


@app.get("/tasks")
def list_tasks():
    return service.list()


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    return service.get(task_id) or not_found(task_id)


@app.post("/tasks", status_code=201)
def create_task(body: TaskCreate):
    return service.create(body.title)


@app.put("/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate):
    return service.update(task_id, body.title, body.done) or not_found(task_id)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    if not service.delete(task_id):
        return not_found(task_id)
    return Response(status_code=204)
