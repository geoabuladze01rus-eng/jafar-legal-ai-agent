"""Authenticated desktop-only reviewer decisions on locally validated claims."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from .claim_review import (
    ClaimReviewInvalid,
    ClaimReviewNotFound,
    ClaimReviewReport,
    ClaimReviewService,
    ClaimReviewTooLarge,
    LocalModel,
)
from .encrypted_claim_decisions import (
    EncryptedClaimDecisionLedger,
    ReviewDecisionInput,
    ReviewDecisionRecord,
    ReviewLedgerTooLarge,
    render_review_decisions_docx,
)
from .encrypted_desktop_corpus import EncryptedDesktopCorpusStore
from .encrypted_sqlite_matter_repository import DesktopStorageError
from .matter_repository import MatterRepository


DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class SaveDecisionRequest(BaseModel):
    report: ClaimReviewReport
    decision: ReviewDecisionInput


def build_claim_decision_router(
    matters: MatterRepository,
    corpus: EncryptedDesktopCorpusStore | None,
    local_model: LocalModel | None,
    ledger: EncryptedClaimDecisionLedger | None,
) -> APIRouter:
    router = APIRouter(tags=["local-claim-decisions"])

    def guard(matter_id: str) -> EncryptedClaimDecisionLedger:
        if ledger is None or corpus is None:
            raise HTTPException(status_code=404, detail="Local review register unavailable")
        if matters.get(matter_id) is None:
            raise HTTPException(status_code=404, detail="Matter not found")
        return ledger

    @router.get(
        "/v1/matters/{matter_id}/claims/decisions",
        response_model=list[ReviewDecisionRecord],
    )
    def list_decisions(matter_id: str) -> list[ReviewDecisionRecord]:
        store = guard(matter_id)
        try:
            return store.list(matter_id)
        except (DesktopStorageError, OSError, ValueError) as exc:
            raise HTTPException(status_code=409, detail="Encrypted review register is corrupt") from exc

    @router.post(
        "/v1/matters/{matter_id}/claims/decisions",
        response_model=ReviewDecisionRecord,
        status_code=201,
    )
    def save_decision(matter_id: str, request: SaveDecisionRequest) -> ReviewDecisionRecord:
        store = guard(matter_id)
        try:
            # Revalidate all source documents and quotes; never trust client
            # reported pair ids or page provenance.
            report = ClaimReviewService(matters, corpus, local_model).revalidate_for_export(
                matter_id, request.report
            )
            pair = next(
                (item for item in report.possible_differences
                 if item.id == request.decision.candidate_id),
                None,
            )
            if pair is None:
                raise ClaimReviewInvalid("Candidate is not in the validated report")
            return store.append(matter_id, pair, request.decision)
        except ClaimReviewNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ClaimReviewTooLarge as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        except ReviewLedgerTooLarge as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        except ClaimReviewInvalid as exc:
            raise HTTPException(status_code=422, detail="Candidate has not passed source verification") from exc
        except (DesktopStorageError, OSError, ValueError) as exc:
            raise HTTPException(status_code=409, detail="Encrypted review source verification failed") from exc

    @router.get("/v1/matters/{matter_id}/claims/decisions/docx")
    def export_decision_register(matter_id: str) -> Response:
        store = guard(matter_id)
        try:
            records = store.list(matter_id)
        except (DesktopStorageError, ValueError, OSError) as exc:
            raise HTTPException(status_code=409, detail="Encrypted review register is corrupt") from exc
        # This is a historical record: never call old statements "verified"
        # merely because they have been retained in a local ledger.
        return Response(
            content=render_review_decisions_docx(matters.get(matter_id).title, records),
            media_type=DOCX_TYPE,
            headers={
                "Content-Disposition": 'attachment; filename="jafar-review-register.docx"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
