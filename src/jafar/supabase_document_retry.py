from __future__ import annotations

from .document_retry import DocumentRetryService
from .document_status import DocumentStatus


class SupabaseRetryStatusStore:
    def __init__(self, client: object) -> None:
        self.client = client

    def get_status(self, *, storage_path: str) -> DocumentStatus:
        response = self.client.table("documents").select("processing_status").eq("storage_path", storage_path).single().execute()
        return DocumentStatus(response.data["processing_status"])

    def set_status(self, *, storage_path: str, status: DocumentStatus, error: str | None = None) -> None:
        if status is DocumentStatus.PROCESSING:
            self.client.rpc("claim_failed_document_for_retry", {"p_storage_path": storage_path}).execute()
            return
        self.client.rpc(
            "finish_document_retry",
            {"p_storage_path": storage_path, "p_success": status is DocumentStatus.COMPLETED, "p_error": error},
        ).execute()


class SupabaseDocumentRetryService(DocumentRetryService):
    """Production retry facade backed by Supabase document state."""

    def __init__(self, client: object, processor: object) -> None:
        super().__init__(SupabaseRetryStatusStore(client), processor)
