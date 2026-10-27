"""Business rules. Unchanged when the storage changes."""
from .repository import TaskRepository


class ValidationError(Exception):
    pass


class TaskService:
    def __init__(self, repo: TaskRepository) -> None:
        self.repo = repo

    def list(self):
        return self.repo.list()

    def get(self, task_id: int):
        return self.repo.get(task_id)

    def create(self, title: str | None):
        if not title or not title.strip():
            raise ValidationError("title is required and must not be empty")
        return self.repo.create(title.strip())

    def update(self, task_id: int, title: str | None, done: bool | None):
        if title is None and done is None:
            raise ValidationError("send at least one of: title, done")
        if title is not None and not title.strip():
            raise ValidationError("title must not be empty")
        return self.repo.update(task_id, title.strip() if title else None, done)

    def delete(self, task_id: int) -> bool:
        return self.repo.delete(task_id)
