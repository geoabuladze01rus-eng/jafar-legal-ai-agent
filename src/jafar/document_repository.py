from __future__ import annotations
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
