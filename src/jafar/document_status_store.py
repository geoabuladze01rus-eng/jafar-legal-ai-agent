from __future__ import annotations

from typing import Protocol

from .document_status import DocumentStatus


class DocumentStatusStore(Protocol):
    def set_status(self, *, message_id: str, storage_path: str, status: DocumentStatus, error: str | None = None) -> None: ...


class NullDocumentStatusStore:
    def set_status(self, *, message_id: str, storage_path: str, status: DocumentStatus, error: str | None = None) -> None:
        return None


class SupabaseDocumentStatusStore:
    def __init__(self, client: object) -> None:
        self.client = client

    def set_status(self, *, message_id: str, storage_path: str, status: DocumentStatus, error: str | None = None) -> None:
        self.client.rpc("set_document_processing_status", {
            "p_message_id": message_id,
            "p_storage_path": storage_path,
            "p_status": status.value,
            "p_error": error,
        })
