from dataclasses import dataclass

from jafar.inbox.classifier import Classification, InboxCategory


@dataclass(frozen=True)
class TriageDecision:
    classification: Classification
    queue: str
    auto_analyze: bool
    requires_human_review: bool


def triage(classification: Classification) -> TriageDecision:
    if classification.category == InboxCategory.SPAM:
        return TriageDecision(classification, "spam", False, False)
    if classification.needs_analysis:
        return TriageDecision(classification, "legal_analysis", True, True)
    return TriageDecision(classification, "general", False, False)
