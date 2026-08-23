from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .attachment_storage import AttachmentStorage
from .document_workflow import DocumentWorkflow, DocumentWorkflowResult
from .inbox import (
    AttachmentProcessingIssue,
    ExtractedInboxDocument,
    InboxDocumentIntake,
    InboxMessage,
)


@dataclass(frozen=True)
class InboxDocumentResult:
    message_id: str
    sender: str
    subject: str
    attachment_name: str
    storage_path: str
    fingerprint: str
    workflow: DocumentWorkflowResult


@dataclass(frozen=True)
class InboxProcessingResult:
    documents: tuple[InboxDocumentResult, ...]
    issues: tuple[AttachmentProcessingIssue, ...]


class InboxProcessor:
    """Bridges email attachments into durable storage and legal document workflow."""

    def __init__(self, intake: InboxDocumentIntake, workflow: DocumentWorkflow, storage: AttachmentStorage) -> None:
        self.intake = intake
        self.workflow = workflow
        self.storage = storage

    def process_message(self, message: InboxMessage) -> InboxProcessingResult:
        intake_result = self.intake.extract_documents(message)
        results: list[InboxDocumentResult] = []
        issues = list(intake_result.issues)
        for item in intake_result.documents:
            try:
                results.append(self._process_document(item))
            except Exception as exc:
                issues.append(AttachmentProcessingIssue(
                    filename=item.attachment.filename,
                    error_type=type(exc).__name__,
                    message=str(exc),
                ))
        return InboxProcessingResult(documents=tuple(results), issues=tuple(issues))

    def _process_document(self, item: ExtractedInboxDocument) -> InboxDocumentResult:
        fingerprint = sha256(item.attachment.content).hexdigest()
        storage_path = self.storage.put(
            path=f"{item.message_id}/{item.attachment.filename}",
            content=item.attachment.content,
            media_type=item.attachment.media_type,
        )
        workflow_result = self.workflow.process(
            document_name=item.attachment.filename,
            extracted=item.document,
        )
        return InboxDocumentResult(
            message_id=item.message_id,
            sender=item.sender,
            subject=item.subject,
            attachment_name=item.attachment.filename,
            storage_path=storage_path,
            fingerprint=fingerprint,
            workflow=workflow_result,
        )
