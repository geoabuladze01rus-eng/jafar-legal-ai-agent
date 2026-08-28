from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .document_intake import DocumentExtractionError, DocumentExtractor, ExtractedDocument


@dataclass(frozen=True)
class InboxAttachment:
    filename: str
    content: bytes
    media_type: str | None = None
    attachment_id: str | None = None
    provider: str = "unknown"


@dataclass(frozen=True)
class AttachmentProcessingIssue:
    filename: str
    error_type: str
    message: str


@dataclass(frozen=True)
class InboxMessage:
    message_id: str
    sender: str
    subject: str
    received_at: datetime
    body_text: str
    attachments: tuple[InboxAttachment, ...] = ()
    provider_issues: tuple[AttachmentProcessingIssue, ...] = ()
    provider: str = "unknown"


@dataclass(frozen=True)
class ExtractedInboxDocument:
    message_id: str
    sender: str
    subject: str
    received_at: datetime
    attachment: InboxAttachment
    document: ExtractedDocument


@dataclass(frozen=True)
class InboxExtractionResult:
    documents: tuple[ExtractedInboxDocument, ...]
    issues: tuple[AttachmentProcessingIssue, ...]


class InboxDocumentIntake:
    """Converts supported email attachments and reports per-file failures."""

    def __init__(self, extractor: DocumentExtractor | None = None) -> None:
        self.extractor = extractor or DocumentExtractor()

    def extract_documents(self, message: InboxMessage) -> InboxExtractionResult:
        documents: list[ExtractedInboxDocument] = []
        issues: list[AttachmentProcessingIssue] = list(message.provider_issues)
        for attachment in message.attachments:
            try:
                document = self.extractor.extract(
                    filename=attachment.filename,
                    content=attachment.content,
                    media_type=attachment.media_type,
                )
            except DocumentExtractionError as exc:
                issues.append(AttachmentProcessingIssue(
                    filename=attachment.filename,
                    error_type=type(exc).__name__,
                    message=str(exc),
                ))
                continue
            documents.append(ExtractedInboxDocument(
                message_id=message.message_id,
                sender=message.sender,
                subject=message.subject,
                received_at=message.received_at,
                attachment=attachment,
                document=document,
            ))
        return InboxExtractionResult(tuple(documents), tuple(issues))
