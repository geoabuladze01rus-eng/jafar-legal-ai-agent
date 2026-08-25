from __future__ import annotations

from datetime import UTC, datetime

from jafar.attachment_materializer import InMemoryAttachmentMaterializer
from jafar.attachment_storage import InMemoryAttachmentStorage
from jafar.document_workflow import DocumentWorkflow
from jafar.domains import MatterType
from jafar.email_pipeline import EmailPipeline
from jafar.email_processing import EmailProcessor
from jafar.inbox import InboxDocumentIntake
from jafar.inbox_processor import InboxProcessor
from jafar.legal_analysis import LegalAnalyzer
from jafar.legal_models import Matter
from jafar.matters import MatterStore
from jafar.outlook_provider import OutlookEmailProvider
from jafar.outlook_readonly import OutlookReadOnlyService


class SyntheticOutlookClient:
    def __init__(self) -> None:
        self.fetched_attachments: list[str] = []

    def list_messages(self, *, limit: int = 25) -> list[dict]:
        return [
            {
                "id": "outlook-msg-1",
                "sender": {"emailAddress": {"address": "client@example.com"}},
                "subject": "Уголовное дело 12604008104000012 — новый документ",
                "receivedDateTime": "2026-08-25T09:00:00Z",
                "bodyPreview": "Во вложении документ по делу.",
                "body": {
                    "contentType": "text",
                    "content": (
                        "По уголовному делу 12604008104000012 прошу проверить документ. "
                        "Срок ответа до 30.08.2026."
                    ),
                },
            }
        ][:limit]

    def list_attachments(self, message_id: str) -> list[dict]:
        assert message_id == "outlook-msg-1"
        return [
            {
                "id": "attachment-1",
                "name": "procedural-note.txt",
                "size_bytes": 256,
                "content_type": "text/plain",
                "is_inline": False,
            }
        ]

    def fetch_attachment(self, message_id: str, attachment_id: str) -> str:
        assert message_id == "outlook-msg-1"
        self.fetched_attachments.append(attachment_id)
        return "file://procedural-note"


def _matter() -> Matter:
    now = datetime.now(UTC)
    return Matter(
        id="matter-pavlik",
        title="Павлик В.А.",
        matter_type=MatterType.CRIMINAL,
        client_name="Павлик В.А.",
        opposing_party=None,
        court_or_authority="Следственный орган",
        case_number="12604008104000012",
        created_at=now,
        updated_at=now,
    )


def _service() -> tuple[OutlookReadOnlyService, MatterStore, SyntheticOutlookClient]:
    store = MatterStore()
    store.create(_matter())
    client = SyntheticOutlookClient()
    provider = OutlookEmailProvider(
        client,
        InMemoryAttachmentMaterializer(
            {
                "file://procedural-note": (
                    "Уголовное дело 12604008104000012. "
                    "Процессуальный срок до 30.08.2026."
                ).encode(),
            }
        ),
    )
    workflow = DocumentWorkflow(store, LegalAnalyzer())
    inbox = InboxProcessor(
        InboxDocumentIntake(),
        workflow,
        InMemoryAttachmentStorage(),
    )
    pipeline = EmailPipeline(EmailProcessor(), inbox)
    return OutlookReadOnlyService(provider, pipeline), store, client


def test_outlook_readonly_e2e_links_matter_analyzes_attachment_and_drafts_for_review():
    service, store, client = _service()

    results = service.run(limit=1)

    assert len(results) == 1
    result = results[0]
    assert result.message_id == "outlook-msg-1"
    assert result.pipeline.email.triage.action == "prepare_legal_analysis"
    assert result.pipeline.email.reply_draft is not None
    assert result.pipeline.email.reply_draft.requires_review is True
    assert len(result.pipeline.documents) == 1
    document = result.pipeline.documents[0]
    assert document.workflow is not None
    assert document.workflow.match is not None
    assert document.workflow.match.matter_id == "matter-pavlik"
    assert len(store.events("matter-pavlik")) == 1
    assert client.fetched_attachments == ["attachment-1"]


def test_outlook_readonly_e2e_is_idempotent_for_same_message():
    service, store, _ = _service()

    first = service.run(limit=1)[0]
    second = service.run(limit=1)[0]

    assert first.pipeline.skipped_as_duplicate is False
    assert second.pipeline.skipped_as_duplicate is True
    assert len(store.events("matter-pavlik")) == 1
