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
