"""Matter-specific encrypted working-draft storage API (desktop only)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import Field, BaseModel

from .encrypted_draft_history import (
    DraftHistoryConflict,
    DraftHistoryLimit,
    DraftHistoryNotFound,
    DraftRevision,
    DraftRevisionInfo,
    DraftSaveRequest,
    DraftSummary,
    EncryptedDraftHistory,
)
from .encrypted_sqlite_matter_repository import DesktopStorageError
from .legal_draft_service import LegalDraftRequest
from .matter_repository import MatterRepository


class DraftHistoryCreateRequest(BaseModel):
    draft: LegalDraftRequest


class DraftRestoreRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    source_revision: int = Field(ge=1)
    approved: bool = False


def build_draft_history_router(
    matters: MatterRepository,
    history: EncryptedDraftHistory | None,
) -> APIRouter:
    router = APIRouter(tags=["desktop-draft-history"])

    def guard(matter_id: str) -> EncryptedDraftHistory:
        if history is None:
            raise HTTPException(status_code=404, detail="Desktop draft history is unavailable")
        if matters.get(matter_id) is None:
            raise HTTPException(status_code=404, detail="Matter not found")
        return history

    def read_or_conflict(op):
        try:
            return op()
        except DraftHistoryNotFound as exc:
            raise HTTPException(status_code=404, detail="Draft not found in selected Matter") from exc
        except (DraftHistoryConflict, DraftHistoryLimit) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (DesktopStorageError, ValueError, OSError) as exc:
            raise HTTPException(status_code=409, detail="Encrypted draft could not be verified") from exc

    @router.get("/v1/matters/{matter_id}/drafts", response_model=list[DraftSummary])
    def list_drafts(matter_id: str):
        return read_or_conflict(lambda: guard(matter_id).list(matter_id))

    @router.post("/v1/matters/{matter_id}/drafts", response_model=DraftRevision, status_code=201)
    def create_draft(matter_id: str, request: DraftHistoryCreateRequest):
        return read_or_conflict(lambda: guard(matter_id).create(matter_id, request.draft))

    @router.get("/v1/matters/{matter_id}/drafts/{draft_id}", response_model=DraftRevision)
    def read_draft(matter_id: str, draft_id: str):
        return read_or_conflict(lambda: guard(matter_id).get(matter_id, draft_id))

    @router.put("/v1/matters/{matter_id}/drafts/{draft_id}", response_model=DraftRevision)
    def save_draft(matter_id: str, draft_id: str, request: DraftSaveRequest):
        return read_or_conflict(
            lambda: guard(matter_id).save(
                matter_id, draft_id,
                expected_revision=request.expected_revision,
                draft=request.draft,
            )
        )

    @router.get(
        "/v1/matters/{matter_id}/drafts/{draft_id}/revisions",
        response_model=list[DraftRevisionInfo],
    )
    def list_versions(matter_id: str, draft_id: str):
        return read_or_conflict(lambda: guard(matter_id).versions(matter_id, draft_id))

    @router.get(
        "/v1/matters/{matter_id}/drafts/{draft_id}/revisions/{revision}",
        response_model=DraftRevision,
    )
    def get_revision(matter_id: str, draft_id: str, revision: int):
        return read_or_conflict(lambda: guard(matter_id).get(matter_id, draft_id, revision))

    @router.post(
        "/v1/matters/{matter_id}/drafts/{draft_id}/restore",
        response_model=DraftRevision,
    )
    def restore_revision(matter_id: str, draft_id: str, request: DraftRestoreRequest):
        if not request.approved:
            raise HTTPException(status_code=403, detail="Revision restoration requires approval")

        def restore():
            local = guard(matter_id)
            source = local.get(matter_id, draft_id, request.source_revision)
            return local.save(
                matter_id, draft_id,
                expected_revision=request.expected_revision,
                draft=source.draft,
            )
        return read_or_conflict(restore)

    return router
