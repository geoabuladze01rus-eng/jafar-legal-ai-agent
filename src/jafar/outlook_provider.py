from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .inbox import InboxAttachment
from .email_adapter import ExternalEmail


class OutlookClient(Protocol):
    """Minimal client contract implemented by the Outlook integration layer."""

    def list_messages(self, *, limit: int = 25) -> list[dict]: ...

    def list_attachments(self, message_id: str) -> list[dict]: ...

    def fetch_attachment(self, message_id: str, attachment_id: str) -> str: ...


@dataclass(frozen=True)
class OutlookProviderConfig:
    supported_extensions: frozenset[str] = frozenset({".pdf", ".docx", ".txt", ".md"})
    max_attachment_bytes: int = 25 * 1024 * 1024


class OutlookEmailProvider:
    """Maps Outlook connector data into Jafar's provider-neutral email contract.

    The provider downloads only supported, non-inline file attachments and leaves
    the actual Outlook authentication/API implementation outside the domain layer.
    """

    def __init__(self, client: OutlookClient, config: OutlookProviderConfig | None = None) -> None:
        self.client = client
        self.config = config or OutlookProviderConfig()

    def fetch_messages(self, *, limit: int = 25) -> list[ExternalEmail]:
        result: list[ExternalEmail] = []
        for raw in self.client.list_messages(limit=limit):
            message_id = str(raw["id"])
            attachments: list[InboxAttachment] = []
            for item in self.client.list_attachments(message_id):
                name = str(item.get("name") or "")
                extension = Path(name).suffix.lower()
                if item.get("is_inline") or extension not in self.config.supported_extensions:
                    continue
                size = int(item.get("size_bytes") or 0)
                if size > self.config.max_attachment_bytes:
                    continue
                file_uri = self.client.fetch_attachment(message_id, str(item["id"]))
                attachments.append(InboxAttachment(name, file_uri.encode(), item.get("content_type")))

            sender = raw.get("sender", {}).get("emailAddress", {}).get("address", "")
            received_at = datetime.fromisoformat(str(raw["receivedDateTime"]).replace("Z", "+00:00"))
            result.append(ExternalEmail(
                message_id=message_id,
                sender=sender,
                subject=str(raw.get("subject") or ""),
                received_at=received_at,
                body_text=str(raw.get("bodyPreview") or ""),
                attachments=tuple(attachments),
            ))
        return result
