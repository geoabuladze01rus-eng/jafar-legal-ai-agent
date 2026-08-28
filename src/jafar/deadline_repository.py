from pydantic import BaseModel


class MatterDeadlineSummary(BaseModel):
    title: str
    due_date: str | None = None
    source_text: str | None = None

class DeadlineRepository:
    def __init__(self, matter_store): self.matter_store = matter_store
    def list_for_matter(self, matter_id: str) -> list[MatterDeadlineSummary]:
        matter = self.matter_store.get(matter_id)
        if matter is None: raise KeyError(matter_id)
        return [MatterDeadlineSummary(title=d.title, due_date=d.due_date.isoformat() if d.due_date else None, source_text=d.source_text) for d in matter.deadlines]
