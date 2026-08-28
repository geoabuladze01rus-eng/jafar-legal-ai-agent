from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Protocol

from .legal_authority_verification import AuthorityStatus, AuthorityVerificationResult


class ApplicabilityStatus(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    SUPERSEDED = "superseded"
    OUTSIDE_TIME = "outside_time"
    REVIEW_REQUIRED = "review_required"


class AuthorityWeight(StrEnum):
    BINDING = "binding"
    HIGH = "high"
    PERSUASIVE = "persuasive"
    CONTEXTUAL = "contextual"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ApplicabilityContext:
    topic: str
    legal_question: str
    relevant_date: date | None = None
    jurisdiction: str = "RU"
    proceeding_type: str | None = None


@dataclass(frozen=True, slots=True)
class AuthorityApplicabilityMetadata:
    authority_type: str
    weight: AuthorityWeight
    effective_from: date | None = None
    effective_to: date | None = None
    topics: tuple[str, ...] = ()
    proceeding_types: tuple[str, ...] = ()
    superseded_by: str | None = None
    negative_treatment: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AuthorityApplicabilityResult:
    verification: AuthorityVerificationResult
    status: ApplicabilityStatus
    weight: AuthorityWeight
    reasons: tuple[str, ...]
    superseded_by: str | None = None


class AuthorityApplicabilityResolver(Protocol):
    def metadata(
        self,
        result: AuthorityVerificationResult,
    ) -> AuthorityApplicabilityMetadata | None:
        """Return canonical applicability metadata for a verified authority."""
        ...


class AuthorityApplicabilityEngine:
    """Assess whether a verified authority is usable for a concrete legal question.

    Verification proves identity/provenance only. Applicability separately checks time,
    topic, proceeding type, authority weight, supersession and negative treatment.
    The engine never infers that an authority controls a case merely because it exists.
    """

    def __init__(self, resolver: AuthorityApplicabilityResolver) -> None:
        self.resolver = resolver

    def assess(
        self,
        verification: AuthorityVerificationResult,
        context: ApplicabilityContext,
    ) -> AuthorityApplicabilityResult:
        if verification.status != AuthorityStatus.VERIFIED:
            return AuthorityApplicabilityResult(
                verification=verification,
                status=ApplicabilityStatus.REVIEW_REQUIRED,
                weight=AuthorityWeight.UNKNOWN,
                reasons=("Источник не прошёл первичную каноническую верификацию.",),
            )

        metadata = self.resolver.metadata(verification)
        if metadata is None:
            return AuthorityApplicabilityResult(
                verification=verification,
                status=ApplicabilityStatus.REVIEW_REQUIRED,
                weight=AuthorityWeight.UNKNOWN,
                reasons=("Нет подтверждённых метаданных о применимости источника.",),
            )

        reasons: list[str] = []
        if metadata.superseded_by:
            reasons.append(f"Источник заменён или преодолён более поздним authority: {metadata.superseded_by}.")
            return AuthorityApplicabilityResult(
                verification=verification,
                status=ApplicabilityStatus.SUPERSEDED,
                weight=metadata.weight,
                reasons=tuple(reasons),
                superseded_by=metadata.superseded_by,
            )

        if metadata.negative_treatment:
            reasons.append("Обнаружено отрицательное последующее толкование или ограничение применимости.")
            reasons.extend(metadata.negative_treatment)
            return AuthorityApplicabilityResult(
                verification=verification,
                status=ApplicabilityStatus.REVIEW_REQUIRED,
                weight=metadata.weight,
                reasons=tuple(reasons),
            )

        if context.relevant_date is not None:
            if metadata.effective_from and context.relevant_date < metadata.effective_from:
                reasons.append("Источник ещё не действовал на юридически значимую дату.")
                return AuthorityApplicabilityResult(
                    verification=verification,
                    status=ApplicabilityStatus.OUTSIDE_TIME,
                    weight=metadata.weight,
                    reasons=tuple(reasons),
                )
            if metadata.effective_to and context.relevant_date > metadata.effective_to:
                reasons.append("Источник уже не действовал на юридически значимую дату.")
                return AuthorityApplicabilityResult(
                    verification=verification,
                    status=ApplicabilityStatus.OUTSIDE_TIME,
                    weight=metadata.weight,
                    reasons=tuple(reasons),
                )

        normalized_topic = context.topic.strip().casefold()
        if metadata.topics and normalized_topic not in {item.strip().casefold() for item in metadata.topics}:
            reasons.append("Источник подтверждён, но не относится к заявленной правовой теме.")
            return AuthorityApplicabilityResult(
                verification=verification,
                status=ApplicabilityStatus.NOT_APPLICABLE,
                weight=metadata.weight,
                reasons=tuple(reasons),
            )

        if context.proceeding_type and metadata.proceeding_types:
            proceeding = context.proceeding_type.strip().casefold()
            if proceeding not in {item.strip().casefold() for item in metadata.proceeding_types}:
                reasons.append("Источник относится к иному виду производства или процессуальному контексту.")
                return AuthorityApplicabilityResult(
                    verification=verification,
                    status=ApplicabilityStatus.NOT_APPLICABLE,
                    weight=metadata.weight,
                    reasons=tuple(reasons),
                )

        reasons.append("Источник подтверждён и прошёл проверки по времени, теме и процессуальному контексту.")
        return AuthorityApplicabilityResult(
            verification=verification,
            status=ApplicabilityStatus.APPLICABLE,
            weight=metadata.weight,
            reasons=tuple(reasons),
        )

    def assess_many(
        self,
        items: tuple[tuple[AuthorityVerificationResult, ApplicabilityContext], ...],
    ) -> tuple[AuthorityApplicabilityResult, ...]:
        return tuple(self.assess(result, context) for result, context in items)

    @staticmethod
    def release_ready(results: tuple[AuthorityApplicabilityResult, ...]) -> bool:
        return bool(results) and all(item.status == ApplicabilityStatus.APPLICABLE for item in results)
