from __future__ import annotations

from dataclasses import dataclass

from .authority_applicability import (
    ApplicabilityContext,
    ApplicabilityStatus,
    AuthorityApplicabilityEngine,
    AuthorityApplicabilityResult,
)
from .court_outline import LegalAuthorityRef
from .legal_authority_verification import AuthorityVerificationResult


@dataclass(frozen=True, slots=True)
class AuthorityApplicabilityPipelineResult:
    results: tuple[AuthorityApplicabilityResult, ...]
    applicable_refs_by_topic: dict[str, tuple[LegalAuthorityRef, ...]]
    blocked_citations: tuple[str, ...]
    release_ready: bool


class AuthorityApplicabilityPipeline:
    """Promote only verified and applicable authorities into drafting inputs."""

    def __init__(self, engine: AuthorityApplicabilityEngine) -> None:
        self.engine = engine

    def run(
        self,
        items: tuple[tuple[str, AuthorityVerificationResult, ApplicabilityContext], ...],
    ) -> AuthorityApplicabilityPipelineResult:
        results: list[AuthorityApplicabilityResult] = []
        refs_by_topic: dict[str, list[LegalAuthorityRef]] = {}
        blocked: list[str] = []

        for topic, verification, context in items:
            result = self.engine.assess(verification, context)
            results.append(result)
            if result.status == ApplicabilityStatus.APPLICABLE:
                refs_by_topic.setdefault(topic, []).append(verification.to_outline_ref())
            else:
                blocked.append(verification.normalized_citation)

        frozen_refs = {topic: tuple(refs) for topic, refs in refs_by_topic.items()}
        result_tuple = tuple(results)
        return AuthorityApplicabilityPipelineResult(
            results=result_tuple,
            applicable_refs_by_topic=frozen_refs,
            blocked_citations=tuple(dict.fromkeys(blocked)),
            release_ready=bool(result_tuple)
            and all(item.status == ApplicabilityStatus.APPLICABLE for item in result_tuple),
        )
