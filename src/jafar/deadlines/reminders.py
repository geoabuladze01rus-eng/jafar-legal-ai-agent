from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from jafar.deadlines.models import Deadline


@dataclass(frozen=True)
class Reminder:
    deadline_id: str
    due_at: datetime
    level: str
    message: str


def build_reminders(deadline: Deadline, now: datetime | None = None) -> list[Reminder]:
    if deadline.due_at is None or deadline.status != "open":
        return []
    now = now or datetime.now(timezone.utc)
    due = deadline.due_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)

    remaining = due - now
    levels = [(timedelta(days=7), "warning"), (timedelta(days=2), "urgent"), (timedelta(hours=24), "critical")]
    reminders = []
    for threshold, level in levels:
        if timedelta(0) < remaining <= threshold:
            reminders.append(Reminder(deadline.deadline_id, due, level, f"Срок '{deadline.title}' приближается."))
    return reminders
