from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .attachment_materializer import AttachmentMaterializer
from .email_adapter import ExternalEmail
from .inbox import AttachmentProcessingIssue, InboxAttachment


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

    Unsupported or unsafe attachments are never silently discarded: a provider
    issue is attached to the normalized email so the legal-review layer can tell
    the lawyer that material exists but was not analyzed.
    """

    def __init__(
        self,
        client: OutlookClient,
        materializer: AttachmentMaterializer,
        config: OutlookProviderConfig | None = None,
    ) -> None:
        self.client = client
        self.materializer = materializer
        self.config = config or OutlookProviderConfig()

    def fetch_messages(self, *, limit: int = 25) -> list[ExternalEmail]:
        result: list[ExternalEmail] = []
        for raw in self.client.list_messages(limit=limit):
            message_id = str(raw["id"])
            attachments: list[InboxAttachment] = []
            provider_issues: list[AttachmentProcessingIssue] = []
            for item in self.client.list_attachments(message_id):
                name = str(item.get("name") or "")
                extension = Path(name).suffix.lower()
                if item.get("is_inline"):
                    continue
                if extension not in self.config.supported_extensions:
                    provider_issues.append(
                        AttachmentProcessingIssue(
                            filename=name or "attachment",
                            error_type="UnsupportedAttachment",
                            message=(
                                f"Outlook attachment type {extension or '<none>'} is not "
                                "supported by the current legal-document intake."
                            ),
                        )
                    )
                    continue
                size = int(item.get("size_bytes") or 0)
                if size > self.config.max_attachment_bytes:
                    provider_issues.append(
                        AttachmentProcessingIssue(
                            filename=name or "attachment",
                            error_type="AttachmentTooLarge",
                            message=(
                                f"Outlook attachment is {size} bytes; maximum supported "
                                f"size is {self.config.max_attachment_bytes} bytes."
                            ),
                        )
                    )
                    continue
                try:
                    file_uri = self.client.fetch_attachment(message_id, str(item["id"]))
                    content = self.materializer.materialize(file_uri)
                except (FileNotFoundError, OSError, RuntimeError) as exc:
                    provider_issues.append(
                        AttachmentProcessingIssue(
                            filename=name or "attachment",
                            error_type=type(exc).__name__,
                            message=str(exc),
                        )
                    )
                    continue
                attachments.append(InboxAttachment(name, content, item.get("content_type")))

            sender = raw.get("sender", {}).get("emailAddress", {}).get("address", "")
            received_at = datetime.fromisoformat(str(raw["receivedDateTime"]))
            result.append(
                ExternalEmail(
                    message_id=message_id,
                    sender=sender,
                    subject=str(raw.get("subject") or ""),
                    received_at=received_at,
                    body_text=self._body_text(raw),
                    attachments=tuple(attachments),
                    provider_issues=tuple(provider_issues),
                )
            )
        return result

    @staticmethod
    def _body_text(raw: dict) -> str:
        """Prefer the full plain-text Outlook body; fall back to the safe preview."""
        body = raw.get("body")
        if isinstance(body, dict):
            content_type = str(body.get("contentType") or "").lower()
            content = body.get("content")
            if content_type == "text" and content:
                return str(content)
        return str(raw.get("bodyPreview") or "")
