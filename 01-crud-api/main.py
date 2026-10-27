"""Task API — BE-01: a CRUD API over an in-memory list (FastAPI)."""
import copy

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A tiny to-do API. Data lives in memory, so it is gone on every restart.",
)

SEED = [
    {"id": 1, "title": "Read the assignment", "done": True},
    {"id": 2, "title": "Build the CRUD API", "done": False},
    {"id": 3, "title": "Push to GitHub", "done": False},
]

# In-memory "database": gone on every restart (that's the lesson of this week).
tasks: list[dict] = copy.deepcopy(SEED)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, examples=["Buy milk"])


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, examples=["Buy oat milk"])
    done: bool | None = Field(default=None, examples=[True])


class Task(BaseModel):
    id: int
    title: str
    done: bool


class Error(BaseModel):
    error: str


ERR_400 = {400: {"model": Error, "description": "Invalid body"}}
ERR_404 = {404: {"model": Error, "description": "Unknown id"}}


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    # The brief wants 400 (not FastAPI's default 422) with a JSON error.
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body") or "body"
    return JSONResponse(status_code=400, content={"error": f"Invalid '{field}': {first['msg']}"})


def bad_request(msg: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": msg})


def not_found(task_id: int) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": f"Task {task_id} not found"})


def find_task(task_id: int):
    return next((t for t in tasks if t["id"] == task_id), None)


@app.get("/", summary="Describe this API")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health", summary="Health check — is the server alive?")
def health():
    return {"status": "ok"}


@app.get("/tasks", response_model=list[Task], summary="List tasks (optional filter & search)")
def list_tasks(
    done: bool | None = Query(default=None, description="Only finished (true) or open (false) tasks"),
    search: str | None = Query(default=None, description="Case-insensitive text search in the title"),
):
    result = tasks
    if done is not None:
        result = [t for t in result if t["done"] == done]
    if search:
        result = [t for t in result if search.lower() in t["title"].lower()]
    return result


@app.get("/tasks/{task_id}", response_model=Task, responses=ERR_404, summary="Get one task by id")
def get_task(task_id: int):
    task = find_task(task_id)
    if task is None:
        return not_found(task_id)
    return task


@app.post("/tasks", status_code=201, response_model=Task, responses=ERR_400, summary="Create a task")
def create_task(body: TaskCreate):
    if not body.title.strip():
        return bad_request("title must not be empty")
    next_id = max((t["id"] for t in tasks), default=0) + 1
    task = {"id": next_id, "title": body.title.strip(), "done": False}
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task, responses={**ERR_400, **ERR_404},
         summary="Update a task's title and/or done flag")
def update_task(task_id: int, body: TaskUpdate):
    task = find_task(task_id)
    if task is None:
        return not_found(task_id)
    if body.title is None and body.done is None:
        return bad_request("send at least one of: title, done")
    if body.title is not None:
        if not body.title.strip():
            return bad_request("title must not be empty")
        task["title"] = body.title.strip()
    if body.done is not None:
        task["done"] = body.done
    return task


@app.delete("/tasks/{task_id}", status_code=204, responses=ERR_404, summary="Delete a task")
def delete_task(task_id: int):
    task = find_task(task_id)
    if task is None:
        return not_found(task_id)
    tasks.remove(task)
    return Response(status_code=204)


# ---------- optional extras ----------

@app.get("/stats", summary="Extra: count total / done / open tasks")
def stats():
    done = sum(1 for t in tasks if t["done"])
    return {"total": len(tasks), "done": done, "open": len(tasks) - done}


@app.post("/reset", summary="Extra: restore the 3 example tasks")
def reset():
    tasks.clear()
    tasks.extend(copy.deepcopy(SEED))
    return tasks
