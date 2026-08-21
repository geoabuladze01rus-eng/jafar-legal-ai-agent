from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


IntakeKind = Literal["email", "document", "plaud", "telegram", "calendar"]


@dataclass(frozen=True, slots=True)
class IntakeEnvelope:
    kind: IntakeKind
    external_id: str
    received_at: datetime
    subject: str | None = None
    sender: str | None = None
    text: str | None = None
    attachments: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IntakeDecision:
    action: Literal["analyze", "ignore", "needs_review"]
    reason: str
    matter_id: str | None = None
    confidence: float = 0.0


class UnifiedIntakeBus:
    """Normalizes external signals before they enter the legal workflow."""

    def classify(self, envelope: IntakeEnvelope) -> IntakeDecision:
        text = (envelope.subject or "") + " " + (envelope.text or "")
        if not text.strip() and not envelope.attachments:
            return IntakeDecision("needs_review", "empty intake payload")
        if envelope.attachments or envelope.kind in {"email", "document", "plaud"}:
            return IntakeDecision("analyze", "legal analysis candidate", confidence=0.5)
        return IntakeDecision("needs_review", "manual classification required")
