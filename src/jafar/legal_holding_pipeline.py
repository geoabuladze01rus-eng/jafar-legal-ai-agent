from __future__ import annotations

from dataclasses import dataclass

from .legal_holding_verifier import HoldingStatus, HoldingVerificationResult, LegalHoldingVerifier
from .legal_proposition_extractor import CaseLawEnrichment


@dataclass(frozen=True, slots=True)
class HoldingPipelineReport:
    results: tuple[HoldingVerificationResult, ...]
    accepted_texts: tuple[str, ...]
    blocked_texts: tuple[str, ...]
    requires_human_review: bool
    may_enter_precedent_pipeline: bool


class LegalHoldingPipeline:
    """Promote only semantically verified holdings to the precedent-candidate boundary."""

    def __init__(self, verifier: LegalHoldingVerifier | None = None) -> None:
        self.verifier = verifier or LegalHoldingVerifier()

    def run(self, enrichment: CaseLawEnrichment) -> HoldingPipelineReport:
        results = self.verifier.verify_many(enrichment.proposition_candidates)
        accepted = tuple(
            item.proposition.text
            for item in results
            if item.status == HoldingStatus.VERIFIED_HOLDING and item.may_enter_holding_base
        )
        blocked = tuple(
            item.proposition.text
            for item in results
            if item.status != HoldingStatus.VERIFIED_HOLDING or not item.may_enter_holding_base
        )
        review = bool(blocked) or not accepted
        return HoldingPipelineReport(
            results=results,
            accepted_texts=accepted,
            blocked_texts=blocked,
            requires_human_review=review,
            may_enter_precedent_pipeline=bool(accepted),
        )
