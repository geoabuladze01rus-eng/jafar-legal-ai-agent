from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True, slots=True)
class LegalDeadline:
    title: str
    due_at: datetime
    source: str
    case_id: str | None = None
    confidence: float = 1.0
    requires_confirmation: bool = False


class DeadlineGuard:
    """Turns calendar/intake signals into auditable legal-deadline candidates."""

    def build_candidate(self, *, title: str, due_at: datetime, source: str, case_id: str | None = None, confidence: float = 0.5) -> LegalDeadline:
        return LegalDeadline(
            title=title,
            due_at=due_at,
            source=source,
            case_id=case_id,
            confidence=confidence,
            requires_confirmation=confidence < 0.9,
        )

    def reminder_windows(self, deadline: LegalDeadline) -> list[dict[str, Any]]:
        return [
            {"kind": "warning", "at": (deadline.due_at - timedelta(days=7)).isoformat()},
            {"kind": "urgent", "at": (deadline.due_at - timedelta(days=1)).isoformat()},
            {"kind": "due", "at": deadline.due_at.isoformat()},
        ]
