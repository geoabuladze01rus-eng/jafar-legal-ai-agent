from __future__ import annotations

from dataclasses import dataclass

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
    workflow: DocumentWorkflowResult


@dataclass(frozen=True)
class InboxProcessingResult:
    documents: tuple[InboxDocumentResult, ...]
    issues: tuple[AttachmentProcessingIssue, ...]


class InboxProcessor:
    """Bridges normalized email messages into the existing legal document workflow."""

    def __init__(self, intake: InboxDocumentIntake, workflow: DocumentWorkflow) -> None:
        self.intake = intake
        self.workflow = workflow

    def process_message(self, message: InboxMessage) -> InboxProcessingResult:
        intake_result = self.intake.extract_documents(message)
        results = tuple(self._process_document(item) for item in intake_result.documents)
        return InboxProcessingResult(documents=results, issues=intake_result.issues)

    def _process_document(self, item: ExtractedInboxDocument) -> InboxDocumentResult:
        workflow_result = self.workflow.process(
            document_name=item.attachment.filename,
            extracted=item.document,
        )
        return InboxDocumentResult(
            message_id=item.message_id,
            sender=item.sender,
            subject=item.subject,
            attachment_name=item.attachment.filename,
            workflow=workflow_result,
        )
