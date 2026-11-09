"""Local-only review of source-checked, model-proposed factual differences."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from .claim_review import (
    ClaimReviewInvalid,
    ClaimReviewNotFound,
    ClaimReviewReport,
    ClaimReviewRequest,
    ClaimReviewService,
    ClaimReviewTooLarge,
    ClaimReviewUnavailable,
    LocalModel,
    render_claim_review_docx,
)
from .encrypted_desktop_corpus import EncryptedDesktopCorpusStore
from .encrypted_sqlite_matter_repository import DesktopStorageError
from .matter_repository import MatterRepository


DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def build_claim_review_router(
    matters: MatterRepository,
    corpus: EncryptedDesktopCorpusStore | None,
    local_model: LocalModel | None,
) -> APIRouter:
    router = APIRouter(tags=["local-claim-review"])

    def service() -> ClaimReviewService:
        if corpus is None:
            raise HTTPException(status_code=404, detail="Local claim review unavailable")
        return ClaimReviewService(matters, corpus, local_model)

    def checked(operation):
        try:
            return operation()
        except ClaimReviewNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ClaimReviewTooLarge as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        except ClaimReviewUnavailable as exc:
            raise HTTPException(status_code=503, detail="Local analysis model unavailable") from exc
        except ClaimReviewInvalid as exc:
            raise HTTPException(
                status_code=422, detail="Proposed statements failed source validation"
            ) from exc
        except (DesktopStorageError, OSError, ValueError) as exc:
            raise HTTPException(status_code=409, detail="Encrypted source integrity check failed") from exc

    @router.post(
        "/v1/matters/{matter_id}/claims/inspect",
        response_model=ClaimReviewReport,
    )
    def inspect_claims(matter_id: str, request: ClaimReviewRequest) -> ClaimReviewReport:
        return checked(lambda: service().inspect(matter_id, request))

    @router.post("/v1/matters/{matter_id}/claims/docx")
    def export_claim_review(matter_id: str, report: ClaimReviewReport) -> Response:
        # Does not trust client-supplied provenance. Recheck encrypted originals
        # and exact quoted text; compute candidate pairings again server-side.
        verified = checked(lambda: service().revalidate_for_export(matter_id, report))
        return Response(
            content=render_claim_review_docx(verified),
            media_type=DOCX_TYPE,
            headers={
                "Content-Disposition": 'attachment; filename="jafar-claim-review.docx"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
