"""Authenticated, desktop-only cross-document evidence comparison API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from .encrypted_desktop_corpus import EncryptedDesktopCorpusStore
from .encrypted_sqlite_matter_repository import DesktopStorageError
from .evidence_matrix import (
    EvidenceMatrixNotFound,
    EvidenceMatrixRequest,
    EvidenceMatrixResponse,
    EvidenceMatrixService,
    EvidenceMatrixTooLarge,
    render_matrix_docx,
)
from .matter_repository import MatterRepository


DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def build_evidence_matrix_router(
    matters: MatterRepository, corpus: EncryptedDesktopCorpusStore | None
) -> APIRouter:
    router = APIRouter(tags=["local-evidence-matrix"])

    def compare(matter_id: str, request: EvidenceMatrixRequest) -> EvidenceMatrixResponse:
        if corpus is None:
            raise HTTPException(status_code=404, detail="Local evidence comparison unavailable")
        try:
            return EvidenceMatrixService(matters, corpus).compare(matter_id, request)
        except EvidenceMatrixNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except EvidenceMatrixTooLarge as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        except (DesktopStorageError, ValueError, OSError) as exc:
            raise HTTPException(status_code=409, detail="Encrypted source verification failed") from exc

    @router.post(
        "/v1/matters/{matter_id}/evidence/matrix",
        response_model=EvidenceMatrixResponse,
    )
    def evidence_matrix(matter_id: str, request: EvidenceMatrixRequest) -> EvidenceMatrixResponse:
        return compare(matter_id, request)

    @router.post("/v1/matters/{matter_id}/evidence/matrix/docx")
    def evidence_matrix_docx(matter_id: str, request: EvidenceMatrixRequest) -> Response:
        report = compare(matter_id, request)
        return Response(
            content=render_matrix_docx(report),
            media_type=DOCX_TYPE,
            headers={
                "Content-Disposition": 'attachment; filename="jafar-evidence-review.docx"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
