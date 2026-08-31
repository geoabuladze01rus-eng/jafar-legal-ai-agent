from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .legal_research_service import LegalResearchResult, LegalResearchService

router = APIRouter(prefix="/v1/matters", tags=["legal-research"])


class LegalResearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=8, ge=1, le=50)
    min_similarity: float = Field(default=0.0, ge=-1.0, le=1.0)


class LegalResearchResponse(BaseModel):
    matter_id: str
    question: str
    answer: str
    citations: list[str]
    contradictions: list[dict[str, Any]]
    retrieved_chunks: int


def _get_service(request: Request, matter_id: str) -> LegalResearchService:
    factory = getattr(request.app.state, "legal_research_service_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Legal research service is not configured")
    try:
        service = factory(matter_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Legal research service is unavailable") from exc
    if service is None:
        raise HTTPException(status_code=503, detail="Legal research service is not configured")
    return service


def _serialize(result: LegalResearchResult) -> LegalResearchResponse:
    return LegalResearchResponse(
        matter_id=result.matter_id,
        question=result.question,
        answer=result.answer,
        citations=list(result.citations),
        contradictions=list(result.contradictions),
        retrieved_chunks=len(result.context.results),
    )


@router.post("/{matter_id}/research", response_model=LegalResearchResponse)
def research_matter(
    matter_id: str,
    body: LegalResearchRequest,
    request: Request,
) -> LegalResearchResponse:
    service = _get_service(request, matter_id)
    try:
        result = service.research(
            matter_id=matter_id,
            question=body.question,
            limit=body.limit,
            min_similarity=body.min_similarity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail="Legal research failed") from exc
    return _serialize(result)
