from __future__ import annotations

from dataclasses import dataclass

from .email_processing import EmailProcessingResult, EmailProcessor
from .inbox import InboxMessage
from .inbox_processor import InboxDocumentResult, InboxProcessor


@dataclass(frozen=True, slots=True)
class EmailPipelineResult:
    email: EmailProcessingResult
    documents: tuple[InboxDocumentResult, ...] = ()


class EmailPipeline:
    """Runs email triage and supported attachment processing as one use case."""

    def __init__(self, email_processor: EmailProcessor, inbox_processor: InboxProcessor) -> None:
        self.email_processor = email_processor
        self.inbox_processor = inbox_processor

    def process(self, message: InboxMessage) -> EmailPipelineResult:
        email_result = self.email_processor.process(message)
        document_results = ()
        if email_result.triage.action == "prepare_legal_analysis":
            document_results = tuple(self.inbox_processor.process_message(message))
        return EmailPipelineResult(email=email_result, documents=document_results)
