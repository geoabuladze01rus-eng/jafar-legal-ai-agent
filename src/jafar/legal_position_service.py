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
    def __init__(self, matter_store, analysis_repository=None, document_repository=None): self.matter_store = matter_store; self.analysis_repository = analysis_repository; self.document_repository = document_repository
    def get(self, matter_id: str) -> LegalPositionRead:
        if self.matter_store.get(matter_id) is None: raise KeyError(matter_id)
        if self.analysis_repository is None: return LegalPositionRead(matter_id=matter_id)
        items = []
        for row in self.analysis_repository.list_for_matter(matter_id):
            if row.get("matter_id") != matter_id: raise ValueError("analysis matter mismatch")
            document_id = row.get("document_id")
            if document_id and self.document_repository is not None:
                document = self.document_repository.get(document_id)
                if document is None or document.matter_id != matter_id: raise ValueError("document provenance mismatch")
            result = row.get("result") or {}
            gaps = result.get("missing_information", [])
            if not isinstance(gaps, list) or not all(isinstance(g, str) for g in gaps): raise ValueError("invalid missing_information")
            items.extend(LegalPositionItem(kind="evidence_gap", text=g) for g in gaps)
            issues = result.get("issues", [])
            if not isinstance(issues, list): raise TypeError("invalid issues")
            for issue in issues:
                if not isinstance(issue, dict): raise TypeError("invalid issue")
                text = issue.get("description") or issue.get("title")
                if not isinstance(text, str) or not text: raise ValueError("invalid issue text")
                items.append(LegalPositionItem(kind="analysis_finding", text=text, review_state="needs_review", sources=[]))
        return LegalPositionRead(matter_id=matter_id, items=items)

class SupabaseAnalysisRepository:
    """Read-only persisted analysis metadata adapter."""
    def __init__(self, client: Any): self.client = client
    def list_for_matter(self, matter_id: str) -> list[dict[str, Any]]:
        response = (self.client.table("ai_analyses").select("id,matter_id,document_id,result,source_chunks,created_at,requires_lawyer_review,review_status").eq("matter_id", matter_id).order("created_at", desc=True).execute())
        return list(response.data or [])

def validate_provenance(*, matter_id: str, document_matter_id: str | None, document_exists: bool = True) -> None:
    if not document_exists: raise ValueError("document reference is missing")
    if document_matter_id is not None and document_matter_id != matter_id: raise ValueError("document does not belong to matter")
