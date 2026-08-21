from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DashboardDeadline:
    matter_id: str
    title: str
    due_at: datetime
    level: str


@dataclass(frozen=True)
class DashboardTask:
    task_id: str
    matter_id: str
    title: str
    due_at: datetime | None
    status: str


@dataclass(frozen=True)
class DashboardInboxItem:
    message_id: str
    subject: str
    sender: str
    category: str
    confidence: float
    needs_analysis: bool


@dataclass(frozen=True)
class DashboardSnapshot:
    generated_at: datetime
    critical_deadlines: tuple[DashboardDeadline, ...] = ()
    tasks: tuple[DashboardTask, ...] = ()
    inbox: tuple[DashboardInboxItem, ...] = ()
    recent_events: tuple[str, ...] = ()
