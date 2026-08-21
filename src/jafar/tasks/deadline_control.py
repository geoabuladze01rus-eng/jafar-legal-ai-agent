from dataclasses import dataclass
from datetime import datetime, timezone

from jafar.tasks.models import Task, TaskStatus


@dataclass(frozen=True)
class TaskDeadlineState:
    task_id: str
    due_at: datetime | None
    status: str
    overdue: bool
    reminder_level: str | None


def evaluate_task_deadline(task: Task, now: datetime | None = None) -> TaskDeadlineState:
    now = now or datetime.now(timezone.utc)
    if task.due_at is None or task.status in {TaskStatus.DONE, TaskStatus.CANCELLED}:
        return TaskDeadlineState(task.task_id, task.due_at, task.status.value, False, None)

    due = task.due_at if task.due_at.tzinfo else task.due_at.replace(tzinfo=timezone.utc)
    remaining = due - now
    if remaining.total_seconds() <= 0:
        return TaskDeadlineState(task.task_id, due, task.status.value, True, "critical")
    if remaining.total_seconds() <= 24 * 3600:
        level = "critical"
    elif remaining.total_seconds() <= 2 * 24 * 3600:
        level = "urgent"
    elif remaining.total_seconds() <= 7 * 24 * 3600:
        level = "warning"
    else:
        level = None
    return TaskDeadlineState(task.task_id, due, task.status.value, False, level)
