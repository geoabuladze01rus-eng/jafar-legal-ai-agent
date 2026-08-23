from __future__ import annotations

from dataclasses import dataclass

from .inbox import InboxMessage


@dataclass(frozen=True, slots=True)
class EmailReplyDraft:
    message_id: str
    to: str
    subject: str
    body: str
    requires_review: bool = True


class EmailReplyDraftGenerator:
    """Creates review-only reply drafts; it never sends email."""

    def create(self, message: InboxMessage, *, summary: str | None = None) -> EmailReplyDraft:
        subject = message.subject.strip()
        reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        body_parts = ["Здравствуйте!", "", "Получил ваше сообщение."]
        if summary:
            body_parts.extend(["", f"Предварительно: {summary}"])
        body_parts.extend(["", "Изучу материалы и подготовлю дальнейшие действия.", "", "С уважением,"])
        return EmailReplyDraft(
            message_id=message.message_id,
            to=message.sender,
            subject=reply_subject,
            body="\n".join(body_parts),
            requires_review=True,
        )
