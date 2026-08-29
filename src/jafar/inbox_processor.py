from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .attachment_storage import AttachmentStorage
from .document_status import DocumentStatus
from .document_status_store import DocumentStatusStore, NullDocumentStatusStore
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
    content_type: str | None
    storage_path: str
    fingerprint: str
    status: DocumentStatus
    error: str | None
    workflow: DocumentWorkflowResult | None


@dataclass(frozen=True)
class InboxProcessingResult:
    documents: tuple[InboxDocumentResult, ...]
    issues: tuple[AttachmentProcessingIssue, ...]


class InboxProcessor:
    def __init__(self, intake: InboxDocumentIntake, workflow: DocumentWorkflow, storage: AttachmentStorage, status_store: DocumentStatusStore | None = None) -> None:
        self.intake = intake
        self.workflow = workflow
        self.storage = storage
        self.status_store = status_store or NullDocumentStatusStore()

    def process_message(self, message: InboxMessage) -> InboxProcessingResult:
        intake_result = self.intake.extract_documents(message)
        results: list[InboxDocumentResult] = []
        issues = list(intake_result.issues)
        for item in intake_result.documents:
            result = self._process_document(item)
            results.append(result)
            if result.status is DocumentStatus.FAILED:
                issues.append(AttachmentProcessingIssue(filename=item.attachment.filename, error_type="DocumentProcessingError", message=result.error or "document processing failed"))
        return InboxProcessingResult(documents=tuple(results), issues=tuple(issues))

    def _process_document(self, item: ExtractedInboxDocument) -> InboxDocumentResult:
        fingerprint = sha256(item.attachment.content).hexdigest()
        storage_path = self.storage.put(path=f"{item.message_id}/{item.attachment.filename}", content=item.attachment.content, media_type=item.attachment.media_type)
        self.status_store.set_status(message_id=item.message_id, storage_path=storage_path, status=DocumentStatus.STORED)
        self.status_store.set_status(message_id=item.message_id, storage_path=storage_path, status=DocumentStatus.PROCESSING)
        try:
            workflow_result = self.workflow.process(document_name=item.attachment.filename, extracted=item.document)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.status_store.set_status(message_id=item.message_id, storage_path=storage_path, status=DocumentStatus.FAILED, error=error)
            return InboxDocumentResult(message_id=item.message_id, sender=item.sender, subject=item.subject, attachment_name=item.attachment.filename, content_type=item.attachment.media_type, storage_path=storage_path, fingerprint=fingerprint, status=DocumentStatus.FAILED, error=error, workflow=None)
        self.status_store.set_status(message_id=item.message_id, storage_path=storage_path, status=DocumentStatus.COMPLETED)
        return InboxDocumentResult(message_id=item.message_id, sender=item.sender, subject=item.subject, attachment_name=item.attachment.filename, content_type=item.attachment.media_type, storage_path=storage_path, fingerprint=fingerprint, status=DocumentStatus.COMPLETED, error=None, workflow=workflow_result)
