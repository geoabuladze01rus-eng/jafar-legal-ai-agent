from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmailTriageDecision:
    message_id: str
    legal_relevance: float
    action: str
    case_candidates: tuple[str, ...] = ()
    attachment_count: int = 0


class EmailTriage:
    """Read-only triage layer. It proposes actions but never sends or moves mail."""

    LEGAL_TERMS = (
        "договор",
        "иск",
        "суд",
        "адвокат",
        "уголов",
        "арбитраж",
        "претенз",
        "следователь",
        "юридическ",
    )
    LEGAL_DOCUMENT_EXTENSIONS = {".pdf", ".docx"}

    def classify(
        self,
        *,
        message_id: str,
        subject: str,
        preview: str,
        attachment_count: int = 0,
        attachment_names: tuple[str, ...] = (),
    ) -> EmailTriageDecision:
        text = f"{subject} {preview}".lower()
        hits = sum(1 for term in self.LEGAL_TERMS if term in text)
        has_legal_attachment = any(
            name.lower().rsplit(".", 1)[-1:]
            and f".{name.lower().rsplit('.', 1)[-1]}" in self.LEGAL_DOCUMENT_EXTENSIONS
            for name in attachment_names
        )
        relevance = min(1.0, hits / 3.0)
        if has_legal_attachment:
            relevance = max(relevance, 0.5)

        # A single explicit legal signal is sufficient to route the message into analysis.
        # Relevance remains a graded score for downstream ranking, but routing fails closed
        # toward lawyer review instead of silently classifying a legal request as generic triage.
        action = "prepare_legal_analysis" if hits > 0 or has_legal_attachment else "triage"
        return EmailTriageDecision(
            message_id,
            relevance,
            action,
            attachment_count=attachment_count,
        )
