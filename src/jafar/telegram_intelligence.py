from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TelegramDecision:
    message_id: str
    relevance: float
    action: str
    reason: str


class TelegramIntelligence:
    """Read-only Telegram triage; publishing/replies remain behind approval."""

    TERMS = ("договор", "иск", "суд", "адвокат", "уголов", "арбитраж", "претенз", "следователь", "дело")

    def classify(self, *, message_id: str, text: str) -> TelegramDecision:
        normalized = text.lower()
        hits = [term for term in self.TERMS if term in normalized]
        relevance = min(1.0, len(hits) / 3.0)
        action = "prepare_case_analysis" if relevance >= 0.34 else "ignore_or_triage"
        reason = ", ".join(hits) if hits else "no_legal_terms"
        return TelegramDecision(message_id, relevance, action, reason)
