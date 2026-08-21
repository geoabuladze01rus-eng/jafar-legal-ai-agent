from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RiskLevel(StrEnum):
    AUTO = "auto"
    REVIEW = "review"
    OWNER = "owner"


@dataclass(frozen=True)
class EditorialDecision:
    level: RiskLevel
    reason: str


OWNER_MARKERS = (
    "персональные данные",
    "паспорт",
    "адрес проживания",
    "телефон",
    "конкретное уголовное дело",
)

REVIEW_MARKERS = (
    "задержали",
    "обыск",
    "допрос",
    "следователь",
    "суд",
    "адвокат",
    "уголовное дело",
)


def decide(text: str) -> EditorialDecision:
    value = text.casefold()

    if any(marker in value for marker in OWNER_MARKERS):
        return EditorialDecision(RiskLevel.OWNER, "contains highly sensitive legal or personal data")

    if any(marker in value for marker in REVIEW_MARKERS):
        return EditorialDecision(RiskLevel.REVIEW, "legal-sensitive topic requires review")

    return EditorialDecision(RiskLevel.AUTO, "routine editorial interaction")
