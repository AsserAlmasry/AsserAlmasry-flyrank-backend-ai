from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Task API", version="1.0")

# In-memory "database": gone on every restart (that's the lesson of this week).
tasks = [
    {"id": 1, "title": "Read the assignment", "done": True},
    {"id": 2, "title": "Build the CRUD API", "done": False},
    {"id": 3, "title": "Push to GitHub", "done": False},
]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    # The brief wants 400 (not FastAPI's default 422) with a JSON error.
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body") or "body"
    return JSONResponse(status_code=400, content={"error": f"Invalid '{field}': {first['msg']}"})


def not_found(task_id: int) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": f"Task {task_id} not found"})


def find_task(task_id: int):
    return next((t for t in tasks if t["id"] == task_id), None)


@app.get("/")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks():
    return tasks


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    task = find_task(task_id)
    if task is None:
        return not_found(task_id)
    return task


@app.post("/tasks", status_code=201)
def create_task(body: TaskCreate):
    if not body.title.strip():
        return JSONResponse(status_code=400, content={"error": "title must not be empty"})
    next_id = max((t["id"] for t in tasks), default=0) + 1
    task = {"id": next_id, "title": body.title.strip(), "done": False}
    tasks.append(task)
    return task
