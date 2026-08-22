from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EmailTriageDecision:
    message_id: str
    legal_relevance: float
    action: str
    case_candidates: tuple[str, ...] = ()
    attachment_count: int = 0


class EmailTriage:
    """Read-only triage layer. It proposes actions but never sends or moves mail."""

    LEGAL_TERMS = ("договор", "иск", "суд", "адвокат", "уголов", "арбитраж", "претенз", "следователь")

    def classify(self, *, message_id: str, subject: str, preview: str, attachment_count: int = 0) -> EmailTriageDecision:
        text = f"{subject} {preview}".lower()
        hits = sum(1 for term in self.LEGAL_TERMS if term in text)
        relevance = min(1.0, hits / 3.0)
        action = "prepare_legal_analysis" if relevance >= 0.34 else "triage"
        return EmailTriageDecision(message_id, relevance, action, attachment_count=attachment_count)
