from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ScheduledPublication:
    publication_id: int
    chat_id: str
    body: str
    scheduled_at: datetime
    media_type: str | None = None
    media_url: str | None = None


def is_due(item: ScheduledPublication, now: datetime | None = None) -> bool:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    scheduled = item.scheduled_at
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    return scheduled <= current
