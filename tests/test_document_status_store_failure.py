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


class FailingWorkflow:
    def process(self, *, document_name, extracted):
        raise RuntimeError("AI provider unavailable")


def test_status_store_records_processing_failed_with_error(synthetic_pdf_bytes):
    statuses = RecordingStatusStore()
    processor = InboxProcessor(InboxDocumentIntake(), FailingWorkflow(), InMemoryAttachmentStorage(), statuses)
    message = InboxMessage(
        message_id="msg-failed-status-test", sender="client@example.test", subject="Contract",
        received_at=datetime.now(UTC), body_text="Review",
        attachments=(InboxAttachment("contract.pdf", synthetic_pdf_bytes, "application/pdf"),),
    )

    processor.process_message(message)

    assert [call[2] for call in statuses.calls] == [
        DocumentStatus.STORED, DocumentStatus.PROCESSING, DocumentStatus.FAILED
    ]
    assert statuses.calls[-1][3] == "RuntimeError: AI provider unavailable"
