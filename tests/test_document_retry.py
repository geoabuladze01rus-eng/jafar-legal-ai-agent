from __future__ import annotations

import pytest

from jafar.document_retry import DocumentRetryService
from jafar.document_status import DocumentStatus


class StatusStore:
    def __init__(self, status: DocumentStatus) -> None:
        self.status = status
        self.calls = []

    def get_status(self, *, storage_path: str) -> DocumentStatus:
        return self.status

    def set_status(self, *, storage_path: str, status: DocumentStatus, error: str | None = None) -> None:
        self.status = status
        self.calls.append((storage_path, status, error))


class Processor:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure

    def process(self, *, storage_path: str) -> str:
        if self.failure:
            raise self.failure
        return "reprocessed"


def test_retry_only_failed_document_and_complete_successfully():
    store = StatusStore(DocumentStatus.FAILED)
    service = DocumentRetryService(store, Processor())

    assert service.retry(storage_path="m/contract.pdf") == "reprocessed"
    assert [call[1] for call in store.calls] == [DocumentStatus.PROCESSING, DocumentStatus.COMPLETED]


def test_retry_failure_returns_document_to_failed_with_error():
    store = StatusStore(DocumentStatus.FAILED)
    service = DocumentRetryService(store, Processor(RuntimeError("provider unavailable")))

    with pytest.raises(RuntimeError, match="provider unavailable"):
        service.retry(storage_path="m/contract.pdf")

    assert [call[1] for call in store.calls] == [DocumentStatus.PROCESSING, DocumentStatus.FAILED]
    assert store.calls[-1][2] == "RuntimeError"


def test_completed_document_cannot_be_retried():
    store = StatusStore(DocumentStatus.COMPLETED)
    service = DocumentRetryService(store, Processor())

    with pytest.raises(ValueError, match="completed document cannot be retried"):
        service.retry(storage_path="m/contract.pdf")

    assert store.calls == []
