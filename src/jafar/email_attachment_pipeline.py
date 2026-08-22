from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class AttachmentRecord:
    attachment_id: str
    file_name: str
    content_type: str | None
    size: int | None
    content_hash: str | None = None
    document_id: str | None = None


class EmailAttachmentPipeline:
    """Normalizes email attachments before document/evidence processing."""

    ALLOWED_DOCUMENT_TYPES = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    def inspect(self, attachments: Iterable[dict[str, Any]]) -> list[AttachmentRecord]:
        result: list[AttachmentRecord] = []
        for item in attachments:
            result.append(
                AttachmentRecord(
                    attachment_id=str(item.get("id", "")),
                    file_name=str(item.get("name", "")),
                    content_type=item.get("content_type") or item.get("contentType"),
                    size=item.get("size"),
                    content_hash=item.get("content_hash"),
                    document_id=item.get("document_id"),
                )
            )
        return result

    @staticmethod
    def hash_content(content: bytes) -> str:
        return sha256(content).hexdigest()

    @classmethod
    def is_document_candidate(cls, content_type: str | None) -> bool:
        return bool(content_type and content_type.lower() in cls.ALLOWED_DOCUMENT_TYPES)
