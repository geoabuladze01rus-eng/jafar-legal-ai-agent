from __future__ import annotations

from dataclasses import dataclass

from .court_outline import CourtOutline, LegalAuthorityRef
from .legal_authority_verification import (
    AuthorityCandidate,
    AuthorityStatus,
    AuthorityVerificationResult,
    LegalAuthorityVerifier,
)


@dataclass(frozen=True, slots=True)
class TopicAuthorityVerification:
    topic: str
    results: tuple[AuthorityVerificationResult, ...]

    @property
    def verified_refs(self) -> tuple[LegalAuthorityRef, ...]:
        return LegalAuthorityVerifier.verified_refs(self.results)

    @property
    def requires_source_verification(self) -> bool:
        return any(result.status != AuthorityStatus.VERIFIED for result in self.results)


class LegalAuthorityPipeline:
    """Verify externally retrieved authority candidates before court-outline use.

    Retrieval itself is intentionally injected from outside this class. This prevents the
    application from treating model-generated citations as authoritative merely because a
    model produced them.
    """

    def __init__(self, verifier: LegalAuthorityVerifier) -> None:
        self.verifier = verifier

    def verify_by_topic(
        self,
        candidates_by_topic: dict[str, tuple[AuthorityCandidate, ...]],
    ) -> dict[str, TopicAuthorityVerification]:
        return {
            topic: TopicAuthorityVerification(
                topic=topic,
                results=self.verifier.verify_many(candidates),
            )
            for topic, candidates in candidates_by_topic.items()
        }

    @staticmethod
    def verified_refs_by_topic(
        reports: dict[str, TopicAuthorityVerification],
    ) -> dict[str, tuple[LegalAuthorityRef, ...]]:
        return {topic: report.verified_refs for topic, report in reports.items()}

    @staticmethod
    def unresolved_citations(
        reports: dict[str, TopicAuthorityVerification],
    ) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                result.candidate.citation
                for report in reports.values()
                for result in report.results
                if result.status != AuthorityStatus.VERIFIED
            )
        )

    @staticmethod
    def outline_is_release_ready(
        outline: CourtOutline,
        reports: dict[str, TopicAuthorityVerification],
    ) -> bool:
        if outline.requires_source_verification:
            return False
        return not any(report.requires_source_verification for report in reports.values())
