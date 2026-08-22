from __future__ import annotations

from enum import StrEnum


class CommentIntent(StrEnum):
    QUESTION = "question"
    LEGAL_HELP = "legal_help"
    AGGRESSIVE = "aggressive"
    PERSONAL_DATA = "personal_data"
    ESCALATE = "escalate"
    DISCUSSION = "discussion"


LEGAL_MARKERS = ("что делать", "как подать", "жалоб", "суд", "адвокат", "юрист", "закон")
HELP_MARKERS = ("мне", "у меня", "моего", "моей", "помогите")
AGGRESSIVE_MARKERS = ("идиот", "мраз", "туп", "ненавижу")
PERSONAL_MARKERS = ("паспорт", "телефон", "адрес", "карта", "номер телефона")
ESCALATE_MARKERS = ("пытк", "уголовн", "угрож", "несовершеннолет")
AMBIGUOUS_LEGAL_MARKERS = ("следователь", "фсин", "колони", "задержали", "обыск", "допрос", "прокуратур", "судебн")


def classify_comment(text: str) -> CommentIntent:
    normalized = " ".join(text.lower().split())
    if any(marker in normalized for marker in PERSONAL_MARKERS):
        return CommentIntent.PERSONAL_DATA
    if any(marker in normalized for marker in ESCALATE_MARKERS):
        return CommentIntent.ESCALATE
    if any(marker in normalized for marker in AGGRESSIVE_MARKERS):
        return CommentIntent.AGGRESSIVE
    if any(marker in normalized for marker in AMBIGUOUS_LEGAL_MARKERS):
        return CommentIntent.ESCALATE
    if any(marker in normalized for marker in LEGAL_MARKERS) and any(marker in normalized for marker in HELP_MARKERS):
        return CommentIntent.LEGAL_HELP
    if "?" in normalized or normalized.startswith(("почему", "как", "можно", "что")):
        return CommentIntent.QUESTION
    return CommentIntent.DISCUSSION
