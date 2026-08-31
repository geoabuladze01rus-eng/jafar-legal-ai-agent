from __future__ import annotations

from datetime import datetime, timezone

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


def test_status_store_records_stored_processing_completed():
    statuses = RecordingStatusStore()
    processor = InboxProcessor(InboxDocumentIntake(), SuccessfulWorkflow(), InMemoryAttachmentStorage(), statuses)
    message = InboxMessage(
        message_id="msg-status-test", sender="client@example.test", subject="Contract",
        received_at=datetime.now(timezone.utc), body_text="Review",
        attachments=(InboxAttachment("contract.txt", b"contract", "text/plain"),),
    )

    processor.process_message(message)

    assert [call[2] for call in statuses.calls] == [
        DocumentStatus.STORED, DocumentStatus.PROCESSING, DocumentStatus.COMPLETED
    ]
    assert all(call[1] == "msg-status-test/contract.txt" for call in statuses.calls)
