from __future__ import annotations

from dataclasses import dataclass

from .authority_applicability import (
    ApplicabilityContext,
    ApplicabilityStatus,
    AuthorityApplicabilityEngine,
    AuthorityApplicabilityResult,
)
from .case_law_ingestion import (
    ActiveCaseProfile,
    CaseImpactAnalyzer,
    CaseImpactSignal,
)
from .legal_authority_verification import AuthorityVerificationResult
from .precedent_freshness import PrecedentFreshnessReport


@dataclass(frozen=True, slots=True)
class ActiveCaseApplicabilityImpact:
    case_id: str
    context: ApplicabilityContext
    applicability: AuthorityApplicabilityResult
    impact: CaseImpactSignal | None


@dataclass(frozen=True, slots=True)
class ActiveCaseApplicabilityReport:
    authority_id: str
    topic: str
    cases: tuple[ActiveCaseApplicabilityImpact, ...]
    requires_lawyer_review: bool


class ActiveCaseApplicabilityPipeline:
    """Assess one authority independently against each active case context.

    A single global applicability result must never be reused across matters with different
    legally relevant dates or proceeding types.
    """

    def __init__(
        self,
        *,
        applicability_engine: AuthorityApplicabilityEngine,
        impact_analyzer: CaseImpactAnalyzer | None = None,
    ) -> None:
        self.applicability_engine = applicability_engine
        self.impact_analyzer = impact_analyzer or CaseImpactAnalyzer()

    def analyze(
        self,
        *,
        verification: AuthorityVerificationResult,
        topic: str,
        active_cases: tuple[ActiveCaseProfile, ...],
        freshness: PrecedentFreshnessReport | None = None,
    ) -> ActiveCaseApplicabilityReport:
        normalized_topic = self._norm(topic)
        results: list[ActiveCaseApplicabilityImpact] = []

        for case in active_cases:
            if normalized_topic not in {self._norm(item) for item in case.topics}:
                continue
            context = ApplicabilityContext(
                topic=topic,
                legal_question=f"Применимость authority к активному делу {case.case_id}",
                relevant_date=case.relevant_date,
                proceeding_type=case.proceeding_type,
            )
            applicability = self.applicability_engine.assess(verification, context)
            impacts = self.impact_analyzer.analyze(
                authority_id=verification.candidate.authority_id,
                topic=topic,
                applicability=applicability,
                freshness=freshness,
                active_cases=(case,),
            )
            results.append(
                ActiveCaseApplicabilityImpact(
                    case_id=case.case_id,
                    context=context,
                    applicability=applicability,
                    impact=impacts[0] if impacts else None,
                )
            )

        review = any(
            item.applicability.status != ApplicabilityStatus.APPLICABLE
            or (item.impact is not None and item.impact.requires_lawyer_review)
            for item in results
        )
        return ActiveCaseApplicabilityReport(
            authority_id=verification.candidate.authority_id,
            topic=topic,
            cases=tuple(results),
            requires_lawyer_review=review,
        )

    @staticmethod
    def _norm(value: str) -> str:
        return " ".join(value.casefold().replace("ё", "е").split())
