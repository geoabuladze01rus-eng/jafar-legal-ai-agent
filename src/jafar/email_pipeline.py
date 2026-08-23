from __future__ import annotations

from dataclasses import dataclass

from .email_processing import EmailProcessingResult, EmailProcessor
from .idempotency import InMemoryProcessingLedger, ProcessingLedger
from .inbox import AttachmentProcessingIssue, InboxMessage
from .inbox_processor import InboxDocumentResult, InboxProcessor


@dataclass(frozen=True, slots=True)
class EmailPipelineResult:
    email: EmailProcessingResult
    documents: tuple[InboxDocumentResult, ...] = ()
    issues: tuple[AttachmentProcessingIssue, ...] = ()
    skipped_as_duplicate: bool = False


class EmailPipeline:
    """Runs email triage and attachment processing with duplicate protection."""

    def __init__(
        self,
        email_processor: EmailProcessor,
        inbox_processor: InboxProcessor,
        ledger: ProcessingLedger | None = None,
    ) -> None:
        self.email_processor = email_processor
        self.inbox_processor = inbox_processor
        self.ledger = ledger or InMemoryProcessingLedger()

    def process(self, message: InboxMessage) -> EmailPipelineResult:
        if self.ledger.has_processed(message.message_id):
            email_result = self.email_processor.process(message)
            return EmailPipelineResult(email=email_result, skipped_as_duplicate=True)

        email_result = self.email_processor.process(message)
        document_results = ()
        issues = ()
        if email_result.triage.action == "prepare_legal_analysis":
            inbox_result = self.inbox_processor.process_message(message)
            document_results = inbox_result.documents
            issues = inbox_result.issues

        self.ledger.mark_processed(message.message_id)
        return EmailPipelineResult(
            email=email_result,
            documents=document_results,
            issues=issues,
        )
