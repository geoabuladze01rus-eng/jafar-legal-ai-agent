from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    PROPOSED = "proposed"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class TaskProposal:
    task_id: str
    matter_id: str
    title: str
    description: str
    due_at: datetime | None
    source_id: str | None
    confidence: float
    requires_approval: bool = True


@dataclass(frozen=True)
class Task:
    task_id: str
    matter_id: str
    title: str
    description: str = ""
    due_at: datetime | None = None
    assignee_id: str | None = None
    status: TaskStatus = TaskStatus.OPEN
    source_id: str | None = None
