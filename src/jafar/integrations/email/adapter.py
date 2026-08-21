from dataclasses import dataclass
from datetime import datetime

from jafar.integrations.email.models import EmailAttachment, LegalEmail


@dataclass(frozen=True)
class MailMessage:
    message_id: str
    sender: str
    subject: str
    received_at: datetime
    body_preview: str
    has_attachments: bool


class MailAdapter:
    """Provider-neutral mailbox boundary. OAuth/API clients live outside this layer."""

    def list_messages(self, limit: int = 20) -> list[MailMessage]:
        raise NotImplementedError

    def list_attachments(self, message_id: str) -> list[EmailAttachment]:
        raise NotImplementedError

    def to_legal_email(self, message: MailMessage) -> LegalEmail:
        attachments = self.list_attachments(message.message_id)
        return LegalEmail(
            message_id=message.message_id,
            sender=message.sender,
            subject=message.subject,
            received_at=message.received_at,
            body_preview=message.body_preview,
            has_attachments=message.has_attachments,
            attachments=attachments,
        )
