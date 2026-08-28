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

def validate_provenance(*, matter_id: str, document_matter_id: str | None, document_exists: bool = True) -> None:
    if not document_exists: raise ValueError("document reference is missing")
    if document_matter_id is not None and document_matter_id != matter_id: raise ValueError("document does not belong to matter")
