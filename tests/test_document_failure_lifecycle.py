from __future__ import annotations

from datetime import datetime, timezone

from jafar.attachment_storage import InMemoryAttachmentStorage
from jafar.document_status import DocumentStatus
from jafar.inbox import InboxAttachment, InboxDocumentIntake, InboxMessage
from jafar.inbox_processor import InboxProcessor


class FailingWorkflow:
    def process(self, *, document_name, extracted):
        raise RuntimeError("OCR provider unavailable")


def test_failed_workflow_preserves_original_and_error():
    storage = InMemoryAttachmentStorage()
    processor = InboxProcessor(InboxDocumentIntake(), FailingWorkflow(), storage)
    attachment = InboxAttachment("contract.pdf", b"original-contract", "application/pdf")
    message = InboxMessage(
        message_id="msg-failure-test",
        sender="client@example.test",
        subject="Contract",
        received_at=datetime.now(timezone.utc),
        body_text="Review attached contract",
        attachments=(attachment,),
    )

    result = processor.process_message(message)

    assert len(result.documents) == 1
    document = result.documents[0]
    assert document.status is DocumentStatus.FAILED
    assert document.error == "RuntimeError: OCR provider unavailable"
    assert document.workflow is None
    assert storage.files[document.storage_path] == (b"original-contract", "application/pdf")
    assert any(issue.filename == "contract.pdf" for issue in result.issues)
