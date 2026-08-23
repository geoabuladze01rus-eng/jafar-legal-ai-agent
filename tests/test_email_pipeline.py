from __future__ import annotations

from datetime import datetime, timezone

from jafar.email_pipeline import EmailPipeline
from jafar.email_processing import EmailProcessor
from jafar.email_reply_draft import EmailReplyDraftGenerator
from jafar.email_triage import EmailTriage
from jafar.inbox import InboxAttachment, InboxDocumentIntake, InboxMessage
from jafar.inbox_processor import InboxProcessor
from jafar.document_intake import ExtractedDocument
from jafar.document_workflow import DocumentWorkflowResult


class StubWorkflow:
    def __init__(self) -> None:
        self.calls = []

    def process(self, *, document_name, extracted):
        self.calls.append((document_name, extracted))
        return DocumentWorkflowResult(
            document_name=document_name,
            extracted=extracted,
            match=None,
            analysis=None,
            event=None,
        )


def message(*, subject="Дело", body="Требуется юридическая помощь.", attachments=()):
    return InboxMessage(
        message_id="msg-1",
        sender="client@example.com",
        subject=subject,
        received_at=datetime.now(timezone.utc),
        body_text=body,
        attachments=tuple(attachments),
    )


def test_relevant_email_creates_review_only_draft():
    result = EmailProcessor(EmailTriage(), EmailReplyDraftGenerator()).process(message())
    assert result.triage.action == "prepare_legal_analysis"
    assert result.reply_draft is not None
    assert result.reply_draft.requires_review is True
    assert result.reply_draft.to == "client@example.com"


def test_irrelevant_email_does_not_create_draft():
    result = EmailProcessor(EmailTriage(), EmailReplyDraftGenerator()).process(
        message(subject="Скидка", body="Получите скидку на услуги.")
    )
    assert result.triage.action != "prepare_legal_analysis"
    assert result.reply_draft is None


def test_pipeline_processes_multiple_supported_attachments():
    workflow = StubWorkflow()
    inbox = InboxProcessor(InboxDocumentIntake(), workflow)
    pipeline = EmailPipeline(EmailProcessor(), inbox)
    msg = message(
        attachments=(
            InboxAttachment("first.txt", b"legal facts", "text/plain"),
            InboxAttachment("second.md", b"legal facts", "text/markdown"),
        )
    )
    result = pipeline.process(msg)
    assert result.email.reply_draft is not None
    assert len(result.documents) == 2
    assert [item.attachment_name for item in result.documents] == ["first.txt", "second.md"]
    assert len(workflow.calls) == 2
    assert all(isinstance(item.workflow, DocumentWorkflowResult) for item in result.documents)


def test_pipeline_ignores_unsupported_attachment_without_aborting_message():
    workflow = StubWorkflow()
    inbox = InboxProcessor(InboxDocumentIntake(), workflow)
    pipeline = EmailPipeline(EmailProcessor(), inbox)
    msg = message(
        attachments=(
            InboxAttachment("legal.txt", b"legal facts", "text/plain"),
            InboxAttachment("archive.zip", b"not supported", "application/zip"),
        )
    )
    result = pipeline.process(msg)
    assert [item.attachment_name for item in result.documents] == ["legal.txt"]
    assert len(workflow.calls) == 1
