from dataclasses import dataclass
from enum import Enum
import re


class InboxCategory(str, Enum):
    GENERAL = "general"
    LEGAL_DOCUMENT = "legal_document"
    NEW_MATTER = "new_matter"
    DEADLINE = "deadline"
    IMPORTANT_NOTICE = "important_notice"
    SPAM = "spam"


@dataclass(frozen=True)
class InboxMessage:
    message_id: str
    sender: str
    subject: str
    body: str
    has_attachments: bool = False


@dataclass(frozen=True)
class Classification:
    message_id: str
    category: InboxCategory
    confidence: float
    needs_analysis: bool
    reason: str


def classify(message: InboxMessage) -> Classification:
    text = f"{message.subject}\n{message.body}".lower()

    if re.search(r"срочно|немедленно|срок|жалоб|судебн|следствен|постановлен|определен", text):
        category = InboxCategory.DEADLINE if re.search(r"срок|до \d|не позднее", text) else InboxCategory.LEGAL_DOCUMENT
        return Classification(message.message_id, category, 0.90, True, "Обнаружены юридические/процессуальные маркеры.")

    if message.has_attachments and re.search(r"договор|иск|жалоб|претензи|постановлен|определен|протокол|документ", text):
        return Classification(message.message_id, InboxCategory.LEGAL_DOCUMENT, 0.88, True, "Вложение и юридические маркеры.")

    if re.search(r"новое дело|новый клиент|обращени|адвокат", text):
        return Classification(message.message_id, InboxCategory.NEW_MATTER, 0.82, True, "Похоже на новое юридическое обращение.")

    if re.search(r"реклам|unsubscribe|выигрыш|казино", text):
        return Classification(message.message_id, InboxCategory.SPAM, 0.95, False, "Обнаружены признаки рекламного/спам-сообщения.")

    return Classification(message.message_id, InboxCategory.GENERAL, 0.60, False, "Недостаточно признаков для юридической классификации.")
