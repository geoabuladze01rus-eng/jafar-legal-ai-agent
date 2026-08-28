from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel


class MatterDocumentSummary(BaseModel):
    id: str
    matter_id: str
    filename: str
    content_type: str | None = None
    source: str | None = None
    created_at: str
    processing_status: str

class DocumentRepository(Protocol):
    def list_for_matter(self, matter_id: str) -> list[MatterDocumentSummary]: ...

class EmptyDocumentRepository:
    def list_for_matter(self, matter_id: str) -> list[MatterDocumentSummary]:
        return []

class SupabaseDocumentRepository:
    """Read-only metadata adapter using the existing Supabase client protocol."""
    def __init__(self, client):
        self.client = client

    def list_for_matter(self, matter_id: str) -> list[MatterDocumentSummary]:
        response = (self.client.table("documents")
                    .select("id,matter_id,filename,content_type,source,created_at,processing_status")
                    .eq("matter_id", matter_id).order("created_at", desc=True).execute())
        return [MatterDocumentSummary(
            id=row["id"], matter_id=row["matter_id"], filename=row["filename"],
            content_type=row.get("content_type"), source=row.get("source"),
            created_at=self._timestamp(row["created_at"]),
            processing_status=row["processing_status"],
        ) for row in (response.data or [])]

    @staticmethod
    def _timestamp(value) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str) and value:
            return value
        raise ValueError("invalid document created_at")
