from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .document_intake import DocumentExtractionError, DocumentExtractor, ExtractedDocument


@dataclass(frozen=True)
class InboxAttachment:
    filename: str
    content: bytes
    media_type: str | None = None


@dataclass(frozen=True)
class InboxMessage:
    message_id: str
    sender: str
    subject: str
    received_at: datetime
    body_text: str
    attachments: tuple[InboxAttachment, ...] = ()


@dataclass(frozen=True)
class ExtractedInboxDocument:
    message_id: str
    sender: str
    subject: str
    received_at: datetime
    attachment: InboxAttachment
    document: ExtractedDocument


class InboxDocumentIntake:
    """Converts supported legal email attachments into the existing document pipeline."""

    def __init__(self, extractor: DocumentExtractor | None = None) -> None:
        self.extractor = extractor or DocumentExtractor()

    def extract_documents(self, message: InboxMessage) -> list[ExtractedInboxDocument]:
        documents: list[ExtractedInboxDocument] = []
        for attachment in message.attachments:
            try:
                document = self.extractor.extract(
                    filename=attachment.filename,
                    content=attachment.content,
                    media_type=attachment.media_type,
                )
            except DocumentExtractionError:
                # Unsupported/non-text attachments are ignored at intake; the caller
                # can report them separately without aborting the whole message.
                continue
            documents.append(
                ExtractedInboxDocument(
                    message_id=message.message_id,
                    sender=message.sender,
                    subject=message.subject,
                    received_at=message.received_at,
                    attachment=attachment,
                    document=document,
                )
            )
        return documents
