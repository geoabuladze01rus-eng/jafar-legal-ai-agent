from __future__ import annotations

from datetime import UTC, datetime

from jafar.attachment_storage import InMemoryAttachmentStorage
from jafar.document_status import DocumentStatus
from jafar.inbox import InboxAttachment, InboxDocumentIntake, InboxMessage
from jafar.inbox_processor import InboxProcessor


class RecordingStatusStore:
    def __init__(self) -> None:
        self.calls = []

    def set_status(self, *, message_id, storage_path, status, error=None):
        self.calls.append((message_id, storage_path, status, error))


class SuccessfulWorkflow:
    def process(self, *, document_name, extracted):
        return type("WorkflowResult", (), {"match": None, "analysis": {"ok": True}})()


def test_status_store_records_stored_processing_completed(synthetic_pdf_bytes):
    statuses = RecordingStatusStore()
    processor = InboxProcessor(InboxDocumentIntake(), SuccessfulWorkflow(), InMemoryAttachmentStorage(), statuses)
    message = InboxMessage(
        message_id="msg-status-test", sender="client@example.test", subject="Contract",
        received_at=datetime.now(UTC), body_text="Review",
        attachments=(InboxAttachment("contract.pdf", synthetic_pdf_bytes, "application/pdf"),),
    )

    processor.process_message(message)

    assert [call[2] for call in statuses.calls] == [
        DocumentStatus.STORED, DocumentStatus.PROCESSING, DocumentStatus.COMPLETED
    ]
    assert all(call[1] == "msg-status-test/contract.pdf" for call in statuses.calls)
