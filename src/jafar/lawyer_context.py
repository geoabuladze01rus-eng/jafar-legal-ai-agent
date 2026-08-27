from __future__ import annotations

from dataclasses import dataclass

from .email_pipeline import EmailPipelineResult
from .inbox import InboxMessage


@dataclass(frozen=True, slots=True)
class LegalEmailAttachmentSnapshot:
    filename: str
    mime_type: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class LegalEmailSnapshot:
    message_id: str
    sender: str
    subject: str
    triage_action: str
    legal_relevance: float
    matter_ids: tuple[str, ...]
    document_count: int
    issue_count: int
    draft_to: str | None
    draft_subject: str | None
    draft_body: str | None
    requires_review: bool
    provider: str = "unknown"
    received_at: str | None = None
    summary: str | None = None
    attachments: tuple[LegalEmailAttachmentSnapshot, ...] = ()
    external_links: tuple[str, ...] = ()


class LawyerContext:
    """Small in-process context shared by read-only ingestion and command surfaces."""

    def __init__(self) -> None:
        self._latest_legal_email: LegalEmailSnapshot | None = None

    @property
    def latest_legal_email(self) -> LegalEmailSnapshot | None:
        return self._latest_legal_email

    def record_email(self, message: InboxMessage, result: EmailPipelineResult) -> None:
        if result.email.triage.action != "prepare_legal_analysis":
            return

        matter_ids = tuple(
            dict.fromkeys(
                document.workflow.match.matter_id
                for document in result.documents
                if document.workflow is not None and document.workflow.match is not None
            )
        )
        draft = result.email.reply_draft
        self._latest_legal_email = LegalEmailSnapshot(
            message_id=message.message_id,
            sender=message.sender,
            subject=message.subject,
            triage_action=result.email.triage.action,
            legal_relevance=result.email.triage.legal_relevance,
            matter_ids=matter_ids,
            document_count=len(result.documents),
            issue_count=len(result.issues),
            draft_to=draft.to if draft else None,
            draft_subject=draft.subject if draft else None,
            draft_body=draft.body if draft else None,
            requires_review=draft.requires_review if draft else True,
            provider="pipeline",
        )

    def record_gmail_email(
        self,
        *,
        message_id: str,
        sender: str,
        subject: str,
        received_at: str,
        legal_relevance: float,
        summary: str,
        attachments: tuple[LegalEmailAttachmentSnapshot, ...],
        external_links: tuple[str, ...],
    ) -> None:
        self._latest_legal_email = LegalEmailSnapshot(
            message_id=message_id,
            sender=sender,
            subject=subject,
            triage_action="prepare_legal_analysis",
            legal_relevance=legal_relevance,
            matter_ids=(),
            document_count=0,
            issue_count=0,
            draft_to=None,
            draft_subject=None,
            draft_body=None,
            requires_review=True,
            provider="gmail",
            received_at=received_at,
            summary=summary,
            attachments=attachments,
            external_links=external_links,
        )
