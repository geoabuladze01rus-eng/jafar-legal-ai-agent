from __future__ import annotations

from datetime import datetime, timezone

from jafar.attachment_storage import InMemoryAttachmentStorage
from jafar.inbox import InboxAttachment, InboxDocumentIntake, InboxMessage
from jafar.inbox_processor import InboxProcessor


class FakeWorkflow:
    def process(self, *, document_name, extracted):
        return type("WorkflowResult", (), {"match": None, "analysis": {"ok": True}})()


def test_processor_persists_original_and_exposes_fingerprint():
    storage = InMemoryAttachmentStorage()
    processor = InboxProcessor(InboxDocumentIntake(), FakeWorkflow(), storage)
    attachment = InboxAttachment("order.txt", b"legal-original", "text/plain")
    message = InboxMessage(
        message_id="msg-storage-test",
        sender="client@example.test",
        subject="Order",
        received_at=datetime.now(timezone.utc),
        body_text="Please review",
        attachments=(attachment,),
    )

    result = processor.process_message(message)

    assert not result.issues
    assert len(result.documents) == 1
    document = result.documents[0]
    assert document.storage_path == "msg-storage-test/order.txt"
    assert document.fingerprint
    assert storage.files[document.storage_path] == (b"legal-original", "text/plain")
