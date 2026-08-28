from typing import Any

from pydantic import BaseModel, Field


class LegalPositionItem(BaseModel):
    kind: str
    text: str
    review_state: str = "needs_review"
    sources: list[dict[str, str]] = Field(default_factory=list)

class LegalPositionRead(BaseModel):
    matter_id: str
    summary: str | None = None
    items: list[LegalPositionItem] = Field(default_factory=list)

class LegalPositionReadService:
    def __init__(self, matter_store): self.matter_store = matter_store
    def get(self, matter_id: str) -> LegalPositionRead:
        if self.matter_store.get(matter_id) is None: raise KeyError(matter_id)
        return LegalPositionRead(matter_id=matter_id)

class SupabaseAnalysisRepository:
    """Read-only persisted analysis metadata adapter."""
    def __init__(self, client: Any): self.client = client
    def list_for_matter(self, matter_id: str) -> list[dict[str, Any]]:
        response = (self.client.table("ai_analyses").select("id,matter_id,document_id,result,source_chunks,created_at,requires_lawyer_review,review_status").eq("matter_id", matter_id).order("created_at", desc=True).execute())
        return list(response.data or [])

def validate_provenance(*, matter_id: str, document_matter_id: str | None, document_exists: bool = True) -> None:
    if not document_exists: raise ValueError("document reference is missing")
    if document_matter_id is not None and document_matter_id != matter_id: raise ValueError("document does not belong to matter")
