from __future__ import annotations

from dataclasses import dataclass

from .court_outline import CourtOutline, LegalAuthorityRef
from .legal_authority_verification import (
    AuthorityCandidate,
    AuthorityStatus,
    AuthorityVerificationResult,
    LegalAuthorityVerifier,
)
from .matter_intelligence_writer import MatterIntelligenceWriter


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

    def __init__(self, verifier: LegalAuthorityVerifier, intelligence_writer: MatterIntelligenceWriter | None = None, owner_id: str = "local-development-user") -> None:
        self.verifier = verifier
        self.intelligence_writer = intelligence_writer
        self.owner_id = owner_id

    def verify_by_topic(
        self,
        candidates_by_topic: dict[str, tuple[AuthorityCandidate, ...]],
        *, matter_id: str | None = None, analysis_run_id: str | None = None,
    ) -> dict[str, TopicAuthorityVerification]:
        reports = {
            topic: TopicAuthorityVerification(
                topic=topic,
                results=self.verifier.verify_many(candidates),
            )
            for topic, candidates in candidates_by_topic.items()
        }
        if self.intelligence_writer and matter_id and analysis_run_id:
            payloads = []
            for topic, report in reports.items():
                for result in report.results:
                    candidate = result.candidate
                    payloads.append({
                        "id": candidate.authority_id,
                        "court": candidate.source_name or "unknown",
                        "date": candidate.effective_date,
                        "number": result.normalized_citation,
                        "document_type": "authority",
                        "source_kind": "official" if result.status == AuthorityStatus.VERIFIED else "discovery",
                        "verification_state": result.status.value,
                        "holding": candidate.proposition,
                        "applicability": None,
                        "freshness": candidate.retrieved_at,
                        "source_url": candidate.source_url,
                        "authority_identity": candidate.authority_id,
                        "topic": topic,
                        "superseded": False,
                        "conflict": result.status == AuthorityStatus.CONFLICTING,
                    })
            self.intelligence_writer.write_many(owner_id=self.owner_id, matter_id=matter_id, kind="authority", payloads=payloads, analysis_run_id=analysis_run_id)
        return reports

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
