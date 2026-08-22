from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    event_type: str
    actor: str
    request_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    case_id: str | None = None
    action: str | None = None
    status: str | None = None
    evidence_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditTrail:
    """Append-only in-process audit model for agent decisions and side effects."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> AuditEvent:
        self._events.append(event)
        return event

    def list_for_request(self, request_id: str) -> list[AuditEvent]:
        return [event for event in self._events if event.request_id == request_id]

    def list_for_case(self, case_id: str) -> list[AuditEvent]:
        return [event for event in self._events if event.case_id == case_id]

    def export(self) -> list[dict[str, Any]]:
        return [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "actor": event.actor,
                "request_id": event.request_id,
                "occurred_at": event.occurred_at.isoformat(),
                "case_id": event.case_id,
                "action": event.action,
                "status": event.status,
                "evidence_ids": list(event.evidence_ids),
                "metadata": event.metadata,
            }
            for event in self._events
        ]
