"""API router for case evidence gap analysis and grounded statement extraction."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .case_evidence_gap_service import (
    CaseEvidenceGapReport,
    CaseEvidenceGapRequest,
    CaseEvidenceGapService,
    LocalAIModel,
    LocalCorpus,
)
from .matter_repository import MatterRepository


def build_case_evidence_gap_router(
    matters: MatterRepository,
    corpus: LocalCorpus | None,
    model: LocalAIModel | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/v1/matters", tags=["analysis"])

    @router.post(
        "/{matter_id}/analysis/evidence-gaps",
        response_model=CaseEvidenceGapReport,
    )
    def analyze_evidence_gaps(
        matter_id: str,
        request: CaseEvidenceGapRequest,
    ) -> CaseEvidenceGapReport:
        if corpus is None:
            raise HTTPException(status_code=404, detail="Desktop corpus storage is unavailable")
        if matters.get(matter_id) is None:
            raise HTTPException(status_code=404, detail="Matter not found")

        service = CaseEvidenceGapService(matters, corpus, model)
        try:
            return service.analyze(matter_id, request)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return router
