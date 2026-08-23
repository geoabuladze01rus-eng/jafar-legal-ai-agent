from __future__ import annotations

from dataclasses import dataclass

from .email_processing import EmailProcessingResult, EmailProcessor
from .idempotency import InMemoryProcessingLedger, ProcessingLedger
from .inbox import AttachmentProcessingIssue, InboxMessage
from .inbox_processor import InboxDocumentResult, InboxProcessor
from .processing_persistence import InMemoryProcessingResultStore, ProcessingResultStore


@dataclass(frozen=True, slots=True)
class EmailPipelineResult:
    email: EmailProcessingResult
    documents: tuple[InboxDocumentResult, ...] = ()
    issues: tuple[AttachmentProcessingIssue, ...] = ()
    skipped_as_duplicate: bool = False


class EmailPipeline:
    """Runs email processing, duplicate protection and optional durable persistence."""

    def __init__(
        self,
        email_processor: EmailProcessor,
        inbox_processor: InboxProcessor,
        ledger: ProcessingLedger | None = None,
        result_store: ProcessingResultStore | None = None,
    ) -> None:
        self.email_processor = email_processor
        self.inbox_processor = inbox_processor
        self.ledger = ledger or InMemoryProcessingLedger()
        self.result_store = result_store or InMemoryProcessingResultStore()

    def process(self, message: InboxMessage) -> EmailPipelineResult:
        received_at = message.received_at.isoformat()
        claimed = self.ledger.claim(
            message.message_id,
            sender=message.sender,
            subject=message.subject,
            received_at=received_at,
        )
        email_result = self.email_processor.process(message)
        if not claimed:
            return EmailPipelineResult(email=email_result, skipped_as_duplicate=True)

        try:
            document_results = ()
            issues = ()
            if email_result.triage.action == "prepare_legal_analysis":
                inbox_result = self.inbox_processor.process_message(message)
                document_results = inbox_result.documents
                issues = inbox_result.issues
            result = EmailPipelineResult(
                email=email_result,
                documents=document_results,
                issues=issues,
            )
            self.result_store.save(message, result)
            self.ledger.mark_processed(message.message_id)
            return result
        except Exception:
            self.ledger.mark_failed(message.message_id)
            raise
