from __future__ import annotations

from dataclasses import dataclass

from .email_adapter import EmailAdapter
from .email_pipeline import EmailPipeline, EmailPipelineResult
from .lawyer_context import LawyerContext
from .outlook_provider import OutlookEmailProvider


@dataclass(frozen=True, slots=True)
class OutlookReadOnlyResult:
    message_id: str
    sender: str
    subject: str
    pipeline: EmailPipelineResult


class OutlookReadOnlyService:
    """Read-only Outlook -> Jafar legal-email pipeline orchestration.

    This service intentionally exposes no send, reply, archive, delete or mutation
    operation. Drafts produced by the downstream pipeline remain review-only.
    """

    def __init__(
        self,
        provider: OutlookEmailProvider,
        pipeline: EmailPipeline,
        context: LawyerContext | None = None,
    ) -> None:
        self.adapter = EmailAdapter(provider)
        self.pipeline = pipeline
        self.context = context

    def run(self, *, limit: int = 25) -> tuple[OutlookReadOnlyResult, ...]:
        results: list[OutlookReadOnlyResult] = []
        for message in self.adapter.fetch(limit=limit):
            result = self.pipeline.process(message)
            if self.context is not None and not result.skipped_as_duplicate:
                self.context.record_email(message, result)
            results.append(
                OutlookReadOnlyResult(
                    message_id=message.message_id,
                    sender=message.sender,
                    subject=message.subject,
                    pipeline=result,
                )
            )
        return tuple(results)
