from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TimelineEventType(str, Enum):
    EMAIL = "email"
    DOCUMENT = "document"
    ANALYSIS = "analysis"
    DEADLINE = "deadline"
    TASK = "task"
    ACTION = "action"
    NOTE = "note"


@dataclass(frozen=True)
class MatterTimelineEvent:
    event_id: str
    matter_id: str
    event_type: TimelineEventType
    title: str
    occurred_at: datetime
    source_id: str | None = None
    summary: str | None = None
    requires_approval: bool = False


def sort_timeline(events: list[MatterTimelineEvent]) -> list[MatterTimelineEvent]:
    return sorted(events, key=lambda event: event.occurred_at, reverse=True)
