from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class EventType(str, Enum):
    EMAIL_RECEIVED = "email_received"
    DOCUMENT_INGESTED = "document_ingested"
    ANALYSIS_COMPLETED = "analysis_completed"
    DRAFT_CREATED = "draft_created"
    ACTION_APPROVED = "action_approved"
    ACTION_EXECUTED = "action_executed"


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: EventType
    actor: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    matter_id: str | None = None
    object_id: str | None = None
    details: dict[str, str] = field(default_factory=dict)


class StateStore:
    """Persistence boundary for workflow state and audit events."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append_event(self, event: AuditEvent) -> AuditEvent:
        self._events.append(event)
        return event

    def events_for_matter(self, matter_id: str) -> list[AuditEvent]:
        return [event for event in self._events if event.matter_id == matter_id]

    def all_events(self) -> list[AuditEvent]:
        return list(self._events)
