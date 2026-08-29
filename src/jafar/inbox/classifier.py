import re
from dataclasses import dataclass
from enum import Enum


class MailCategory(str, Enum):
    LEGAL = "legal"
    BUSINESS = "business"
    PERSONAL = "personal"
    OTHER = "other"


@dataclass(frozen=True)
class MailClassification:
    message_id: str
    category: MailCategory
    confidence: float
    existing_matter_id: str | None
    has_attachments: bool
    needs_analysis: bool
    reasons: tuple[str, ...] = ()


LEGAL_TERMS = (
    "суд", "иск", "претенз", "договор", "адвокат", "следств", "полици",
    "прокуратур", "тамож", "арбитраж", "уголовн", "гражданск", "исполнительн",
    "доверенность", "ходатайств", "постановлен", "определен", "решени",
)


def classify_mail(message_id: str, subject: str, preview: str, *, has_attachments: bool = False, matter_id: str | None = None) -> MailClassification:
    text = f"{subject} {preview}".lower()
    matches = tuple(term for term in LEGAL_TERMS if re.search(term, text))
    if matches:
        confidence = min(0.98, 0.70 + 0.04 * len(matches))
        return MailClassification(message_id, MailCategory.LEGAL, confidence, matter_id, has_attachments, True, ("Найдены юридические термины: " + ", ".join(matches),))
    return MailClassification(message_id, MailCategory.OTHER, 0.60, matter_id, has_attachments, False, ())
