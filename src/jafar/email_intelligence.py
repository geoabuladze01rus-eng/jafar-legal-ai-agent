from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EmailAssessment:
    relevant: bool
    confidence: float
    case_candidates: tuple[str, ...]
    document_candidates: tuple[str, ...]
    risks: tuple[str, ...]
    suggested_action: str


class EmailIntelligence:
    """Classifies mail for legal workflow; it proposes, never sends or decides."""

    LEGAL_TERMS = ("дело", "суд", "иск", "следователь", "адвокат", "договор", "претенз", "арбитраж", "уголовн", "гражданск")

    def assess(self, message: dict[str, Any]) -> EmailAssessment:
        text = " ".join(str(message.get(key, "")) for key in ("subject", "bodyPreview", "body")) .lower()
        hits = tuple(term for term in self.LEGAL_TERMS if term in text)
        relevant = bool(hits)
        confidence = min(0.99, 0.55 + 0.07 * len(set(hits))) if relevant else 0.05
        action = "prepare_legal_analysis" if relevant else "ignore_or_triage"
        return EmailAssessment(relevant, confidence, (), (), hits, action)
