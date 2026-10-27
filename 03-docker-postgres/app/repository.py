"""The repository interface, plus the original in-memory implementation."""
from typing import Protocol


class TaskRepository(Protocol):
    """Anything that stores tasks. The service and routes only depend on this."""

    def list(self) -> list[dict]: ...
    def get(self, task_id: int) -> dict | None: ...
    def create(self, title: str) -> dict: ...
    def update(self, task_id: int, title: str | None, done: bool | None) -> dict | None: ...
    def delete(self, task_id: int) -> bool: ...


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks = [
            {"id": 1, "title": "Read the assignment", "done": True},
            {"id": 2, "title": "Build the CRUD API", "done": False},
            {"id": 3, "title": "Push to GitHub", "done": False},
        ]

    def list(self) -> list[dict]:
        return [dict(t) for t in self._tasks]

    def get(self, task_id: int) -> dict | None:
        return next((dict(t) for t in self._tasks if t["id"] == task_id), None)

    def create(self, title: str) -> dict:
        task = {"id": max((t["id"] for t in self._tasks), default=0) + 1, "title": title, "done": False}
        self._tasks.append(task)
        return dict(task)

    def update(self, task_id: int, title: str | None, done: bool | None) -> dict | None:
        task = next((t for t in self._tasks if t["id"] == task_id), None)
        if task is None:
            return None
        if title is not None:
            task["title"] = title
        if done is not None:
            task["done"] = done
        return dict(task)

    def delete(self, task_id: int) -> bool:
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if t["id"] != task_id]
        return len(self._tasks) < before
