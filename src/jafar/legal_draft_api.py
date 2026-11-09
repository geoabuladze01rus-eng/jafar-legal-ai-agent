"""Authenticated local-only preview and DOCX export endpoints for Matter drafts."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from .encrypted_desktop_corpus import EncryptedDesktopCorpusStore
from .encrypted_sqlite_matter_repository import DesktopStorageError
from .legal_draft_service import (
    DraftNotFound,
    LegalDraftRequest,
    LegalDraftService,
    LegalDraftPreview,
    render_legal_draft_docx,
)
from .matter_repository import MatterRepository


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def build_legal_draft_router(
    matters: MatterRepository,
    corpus: EncryptedDesktopCorpusStore | None,
) -> APIRouter:
    router = APIRouter(tags=["local-legal-drafts"])

    def preview(matter_id: str, request: LegalDraftRequest) -> LegalDraftPreview:
        # Never expose local Matter material through the cloud/server runtime.
        if corpus is None:
            raise HTTPException(status_code=404, detail="Local document composer unavailable")
        try:
            return LegalDraftService(matters, corpus).preview(matter_id, request)
        except DraftNotFound as exc:
            raise HTTPException(status_code=404, detail=exc.detail) from exc
        except (DesktopStorageError, OSError, ValueError) as exc:
            raise HTTPException(
                status_code=409, detail="Local source document integrity verification failed"
            ) from exc

    @router.post(
        "/v1/matters/{matter_id}/drafts/preview",
        response_model=LegalDraftPreview,
    )
    def draft_preview(matter_id: str, request: LegalDraftRequest) -> LegalDraftPreview:
        return preview(matter_id, request)

    @router.post("/v1/matters/{matter_id}/drafts/export")
    def draft_export(matter_id: str, request: LegalDraftRequest) -> Response:
        checked = preview(matter_id, request)
        if not checked.can_export:
            raise HTTPException(
                status_code=422,
                detail="Fill required fields and select at least one indexed source document",
            )
        try:
            docx_data = render_legal_draft_docx(checked)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Draft is not ready to export") from exc
        return Response(
            content=docx_data,
            media_type=DOCX_MIME,
            headers={
                "Content-Disposition": 'attachment; filename="jafar-working-draft.docx"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
