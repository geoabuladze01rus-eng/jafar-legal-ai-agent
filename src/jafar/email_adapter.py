from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .inbox import AttachmentProcessingIssue, InboxAttachment, InboxMessage


@dataclass(frozen=True)
class ExternalEmail:
    message_id: str
    sender: str
    subject: str
    received_at: datetime
    body_text: str
    attachments: tuple[InboxAttachment, ...] = ()
    provider_issues: tuple[AttachmentProcessingIssue, ...] = ()


class EmailProvider(Protocol):
    """Provider-neutral email source contract."""

    def fetch_messages(self, *, limit: int = 25) -> list[ExternalEmail]: ...


class EmailAdapter:
    """Normalizes provider messages into Jafar's inbox domain model."""

    def __init__(self, provider: EmailProvider) -> None:
        self.provider = provider

    def fetch(self, *, limit: int = 25) -> list[InboxMessage]:
        return [
            InboxMessage(
                message_id=message.message_id,
                sender=message.sender,
                subject=message.subject,
                received_at=message.received_at,
                body_text=message.body_text,
                attachments=message.attachments,
                provider_issues=message.provider_issues,
            )
            for message in self.provider.fetch_messages(limit=limit)
        ]
