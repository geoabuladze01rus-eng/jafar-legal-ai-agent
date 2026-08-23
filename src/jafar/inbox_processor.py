from __future__ import annotations

from dataclasses import dataclass

from .document_workflow import DocumentWorkflow, DocumentWorkflowResult
from .inbox import ExtractedInboxDocument, InboxDocumentIntake, InboxMessage


@dataclass(frozen=True)
class InboxDocumentResult:
    message_id: str
    sender: str
    subject: str
    attachment_name: str
    workflow: DocumentWorkflowResult


class InboxProcessor:
    """Bridges normalized email messages into the existing legal document workflow."""

    def __init__(self, intake: InboxDocumentIntake, workflow: DocumentWorkflow) -> None:
        self.intake = intake
        self.workflow = workflow

    def process_message(self, message: InboxMessage) -> list[InboxDocumentResult]:
        results: list[InboxDocumentResult] = []
        for item in self.intake.extract_documents(message):
            results.append(self._process_document(item))
        return results

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
