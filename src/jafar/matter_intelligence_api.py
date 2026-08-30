"""Read-only, owner-scoped projections for the Matter Intelligence UI.

The current persistence layer exposes matter metadata and matter events.  Rich evidence,
authority and council objects are not persisted by the API yet, so those projections return
an explicit empty result instead of inventing production data or triggering analysis.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from .legal_models import Matter
from .matter_intelligence_store import MatterIntelligenceRepository
from .matter_repository import MatterRepository

router = APIRouter(prefix="/v1/matters", tags=["matter-intelligence"])
MatterId = Annotated[str, Path(min_length=1, max_length=200, pattern=r"^\S+$")]
BoundedLimit = Annotated[int, Query(ge=1, le=100)]


class IntelligenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "live"
    available: bool = True


class DocumentProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    filename: str
    document_type: str = "unknown"
    status: str = "event-linked"
    analysis_status: str = "unknown"
    created_at: datetime
    provenance: str = "matter event"


class EvidenceProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    summary: str
    source_document_id: str | None = None
    page_or_fragment: str | None = None
    supports: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    verification_state: str = "requires_review"


class TimelineProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    event_at: datetime
    event: str
    source: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    verification_state: str = "confirmed"


class ContradictionProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    statement_a: str
    source_a: str | None = None
    statement_b: str
    source_b: str | None = None
    category: str = "requires_review"
    significance: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    verification_state: str = "requires_review"


class AuthorityProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    court: str
    date: str | None = None
    number: str | None = None
    document_type: str | None = None
    source_kind: str = "discovery"
    verification_state: str = "requires_review"
    holding: str | None = None
    applicability: str | None = None
    freshness: str | None = None
    source_url: str | None = None


class CouncilProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participating_models: list[str] = Field(default_factory=list)
    conclusions: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    available: bool = False
    verification_state: str = "not_generated"


class PositionProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: str | None = None
    state: str = "not_generated"
    reviewed: bool = False
    lawyer_approved: bool = False


class HearingProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str | None = None
    theses: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    available: bool = False


class CostProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    today_usd: float = 0.0
    month_usd: float = 0.0
    reserved_usd: float = 0.0
    settled_usd: float = 0.0
    remaining_usd: float | None = None
    provider_breakdown: list[dict[str, str | float]] = Field(default_factory=list)
    source: str = "live"


class IntelligenceEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matter_id: str
    source: IntelligenceSource = IntelligenceSource()


class DocumentsResponse(IntelligenceEnvelope):
    items: list[DocumentProjection] = Field(default_factory=list)


class EvidenceResponse(IntelligenceEnvelope):
    items: list[EvidenceProjection] = Field(default_factory=list)


class TimelineResponse(IntelligenceEnvelope):
    items: list[TimelineProjection] = Field(default_factory=list)


class ContradictionsResponse(IntelligenceEnvelope):
    items: list[ContradictionProjection] = Field(default_factory=list)


class AuthoritiesResponse(IntelligenceEnvelope):
    items: list[AuthorityProjection] = Field(default_factory=list)


class CouncilResponse(IntelligenceEnvelope):
    result: CouncilProjection = CouncilProjection()


class PositionResponse(IntelligenceEnvelope):
    result: PositionProjection = PositionProjection()


class HearingResponse(IntelligenceEnvelope):
    result: HearingProjection = HearingProjection()


class CostResponse(IntelligenceEnvelope):
    result: CostProjection = CostProjection()


def build_router(matter_store: MatterRepository, intelligence_store: MatterIntelligenceRepository | None = None, owner_id: str = "local-development-user") -> APIRouter:
    def matter_or_404(matter_id: str) -> Matter:
        matter = matter_store.get(matter_id)
        if matter is None:
            raise HTTPException(status_code=404, detail="Matter not found")
        return matter

    @router.get("/{matter_id}/intelligence/documents", response_model=DocumentsResponse)
    def documents(matter_id: MatterId, limit: BoundedLimit = 50) -> DocumentsResponse:
        matter = matter_or_404(matter_id)
        events = matter_store.events(matter.id)
        items = [
            DocumentProjection(
                id=event.id,
                filename=event.source_document or event.title,
                created_at=event.created_at,
            )
            for event in sorted(events, key=lambda item: (item.event_date, item.id), reverse=True)
            if event.source_document
        ][:limit]
        return DocumentsResponse(matter_id=matter.id, items=items)

    @router.get("/{matter_id}/intelligence/evidence", response_model=EvidenceResponse)
    def evidence(matter_id: MatterId, limit: BoundedLimit = 50) -> EvidenceResponse:
        matter_or_404(matter_id)
        records = intelligence_store.list(owner_id=owner_id, matter_id=matter_id, kind="evidence", limit=limit) if intelligence_store else []
        return EvidenceResponse(matter_id=matter_id, items=[EvidenceProjection.model_validate(item.payload) for item in records])

    @router.get("/{matter_id}/intelligence/timeline", response_model=TimelineResponse)
    def timeline(matter_id: MatterId, limit: BoundedLimit = 50) -> TimelineResponse:
        matter = matter_or_404(matter_id)
        events = sorted(matter_store.events(matter.id), key=lambda item: (item.event_date, item.id))
        items = [
            TimelineProjection(id=event.id, event_at=event.event_date, event=event.title, source=event.source_document)
            for event in events[:limit]
        ]
        return TimelineResponse(matter_id=matter.id, items=items)

    @router.get("/{matter_id}/intelligence/contradictions", response_model=ContradictionsResponse)
    def contradictions(matter_id: MatterId, limit: BoundedLimit = 50) -> ContradictionsResponse:
        matter_or_404(matter_id)
        records = intelligence_store.list(owner_id=owner_id, matter_id=matter_id, kind="contradiction", limit=limit) if intelligence_store else []
        return ContradictionsResponse(matter_id=matter_id, items=[ContradictionProjection.model_validate(item.payload) for item in records])

    @router.get("/{matter_id}/intelligence/authorities", response_model=AuthoritiesResponse)
    def authorities(matter_id: MatterId, limit: BoundedLimit = 50) -> AuthoritiesResponse:
        matter_or_404(matter_id)
        records = intelligence_store.list(owner_id=owner_id, matter_id=matter_id, kind="authority", limit=limit) if intelligence_store else []
        return AuthoritiesResponse(matter_id=matter_id, items=[AuthorityProjection.model_validate(item.payload) for item in records])

    @router.get("/{matter_id}/intelligence/council", response_model=CouncilResponse)
    def council(matter_id: MatterId) -> CouncilResponse:
        matter_or_404(matter_id)
        return CouncilResponse(matter_id=matter_id)

    @router.get("/{matter_id}/intelligence/position", response_model=PositionResponse)
    def position(matter_id: MatterId) -> PositionResponse:
        matter_or_404(matter_id)
        return PositionResponse(matter_id=matter_id)

    @router.get("/{matter_id}/intelligence/hearing", response_model=HearingResponse)
    def hearing(matter_id: MatterId) -> HearingResponse:
        matter_or_404(matter_id)
        return HearingResponse(matter_id=matter_id)

    @router.get("/{matter_id}/intelligence/cost", response_model=CostResponse)
    def cost(matter_id: MatterId) -> CostResponse:
        matter_or_404(matter_id)
        return CostResponse(matter_id=matter_id)

    return router
