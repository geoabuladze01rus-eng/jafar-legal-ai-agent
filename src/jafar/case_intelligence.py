from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class CaseEvent:
    kind: str
    title: str
    occurred_at: datetime | None = None
    source: str | None = None
    evidence_id: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CaseDeadline:
    title: str
    due_at: datetime
    source: str
    confidence: float = 1.0
    requires_confirmation: bool = False


class CaseIntelligence:
    """Aggregates auditable case signals without silently asserting legal facts."""

    def build_snapshot(
        self,
        *,
        case_id: str,
        events: list[CaseEvent] | None = None,
        deadlines: list[CaseDeadline] | None = None,
        entities: list[dict[str, Any]] | None = None,
        documents: list[dict[str, Any]] | None = None,
        risks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        ordered_events = sorted(
            events or [],
            key=lambda event: event.occurred_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        ordered_deadlines = sorted(deadlines or [], key=lambda deadline: deadline.due_at)
        return {
            "case_id": case_id,
            "events": [self._event(event) for event in ordered_events],
            "deadlines": [self._deadline(deadline) for deadline in ordered_deadlines],
            "entities": entities or [],
            "documents": documents or [],
            "risks": risks or [],
            "requires_human_review": any(
                deadline.requires_confirmation for deadline in ordered_deadlines
            ),
        }

    @staticmethod
    def _event(event: CaseEvent) -> dict[str, Any]:
        return {
            "kind": event.kind,
            "title": event.title,
            "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
            "source": event.source,
            "evidence_id": event.evidence_id,
            "confidence": event.confidence,
            "metadata": event.metadata,
        }

    @staticmethod
    def _deadline(deadline: CaseDeadline) -> dict[str, Any]:
        return {
            "title": deadline.title,
            "due_at": deadline.due_at.isoformat(),
            "source": deadline.source,
            "confidence": deadline.confidence,
            "requires_confirmation": deadline.requires_confirmation,
        }
