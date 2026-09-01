from __future__ import annotations

from typing import Protocol

from .document_status import DocumentStatus
from .error_safety import safe_exception_label


class RetryStatusStore(Protocol):
    def get_status(self, *, storage_path: str) -> DocumentStatus: ...
    def set_status(self, *, storage_path: str, status: DocumentStatus, error: str | None = None) -> None: ...


class DocumentRetryService:
    """Retries only failed documents and refuses to reprocess completed ones."""

    def __init__(self, status_store: RetryStatusStore, processor: object) -> None:
        self.status_store = status_store
        self.processor = processor

    def retry(self, *, storage_path: str) -> object:
        status = self.status_store.get_status(storage_path=storage_path)
        if status is DocumentStatus.COMPLETED:
            raise ValueError("completed document cannot be retried")
        if status is not DocumentStatus.FAILED:
            raise ValueError(f"only failed documents can be retried; current status is {status.value}")
        self.status_store.set_status(storage_path=storage_path, status=DocumentStatus.PROCESSING)
        try:
            result = self.processor.process(storage_path=storage_path)
        except Exception as exc:
            self.status_store.set_status(
                storage_path=storage_path,
                status=DocumentStatus.FAILED,
                error=safe_exception_label(exc),
            )
            raise
        self.status_store.set_status(storage_path=storage_path, status=DocumentStatus.COMPLETED)
        return result
