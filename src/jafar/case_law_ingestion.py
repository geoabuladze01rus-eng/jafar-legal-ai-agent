from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from hashlib import sha256
from typing import Any

from .authority_applicability import ApplicabilityStatus, AuthorityApplicabilityResult
from .legal_authority_verification import AuthorityStatus, AuthorityVerificationResult
from .precedent_freshness import FreshnessStatus, PrecedentFreshnessReport


class IngestionStatus(StrEnum):
    NEW = "new"
    DUPLICATE = "duplicate"
    UPDATED = "updated"
    BLOCKED = "blocked"


class CaseImpactLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class CaseLawRecord:
    record_id: str
    citation: str
    court: str
    decided_on: date
    topic: str
    proposition: str
    source_url: str
    source_fingerprint: str
    authority_id: str

    @property
    def dedupe_key(self) -> str:
        raw = "\n".join(
            (
                self.citation.strip().casefold(),
                self.court.strip().casefold(),
                self.decided_on.isoformat(),
                self.source_fingerprint.strip().casefold(),
            )
        )
        return sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ActiveCaseProfile:
    case_id: str
    title: str
    topics: tuple[str, ...]
    proceeding_type: str | None = None
    relevant_date: date | None = None
    authority_ids_in_use: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CaseImpactSignal:
    case_id: str
    authority_id: str
    topic: str
    impact_level: CaseImpactLevel
    reasons: tuple[str, ...]
    requires_lawyer_review: bool


@dataclass(frozen=True, slots=True)
class CaseLawIngestionResult:
    record: CaseLawRecord
    ingestion_status: IngestionStatus
    verification_status: AuthorityStatus
    applicability_status: ApplicabilityStatus
    freshness_status: FreshnessStatus | None
    case_impacts: tuple[CaseImpactSignal, ...]
    requires_human_review: bool


class CaseLawRepository:
    """Small in-memory contract for deduplicated case-law records.

    Production storage can implement the same lookup/upsert semantics in a database.
    """

    def __init__(self) -> None:
        self._by_key: dict[str, CaseLawRecord] = {}
        self._by_id: dict[str, CaseLawRecord] = {}

    def get_by_dedupe_key(self, key: str) -> CaseLawRecord | None:
        return self._by_key.get(key)

    def upsert(self, record: CaseLawRecord) -> IngestionStatus:
        existing = self._by_key.get(record.dedupe_key)
        if existing is not None:
            return IngestionStatus.DUPLICATE

        previous = self._by_id.get(record.record_id)
        if previous is not None and previous.dedupe_key != record.dedupe_key:
            self._by_key.pop(previous.dedupe_key, None)

        self._by_key[record.dedupe_key] = record
        self._by_id[record.record_id] = record
        return IngestionStatus.UPDATED if previous is not None else IngestionStatus.NEW

    def records(self) -> tuple[CaseLawRecord, ...]:
        return tuple(self._by_id.values())


class CaseImpactAnalyzer:
    """Identify active matters that should be re-reviewed after new verified case law arrives."""

    def analyze(
        self,
        *,
        authority_id: str,
        topic: str,
        applicability: AuthorityApplicabilityResult,
        freshness: PrecedentFreshnessReport | None,
        active_cases: tuple[ActiveCaseProfile, ...],
    ) -> tuple[CaseImpactSignal, ...]:
        normalized_topic = topic.strip().casefold()
        freshness_item = None
        if freshness is not None:
            freshness_item = next(
                (
                    item
                    for item in freshness.items
                    if item.precedent.authority_id == authority_id
                ),
                None,
            )

        results: list[CaseImpactSignal] = []
        for case in active_cases:
            case_topics = {item.strip().casefold() for item in case.topics}
            if normalized_topic not in case_topics:
                continue

            reasons: list[str] = []
            level = CaseImpactLevel.LOW
            review = False

            if applicability.status != ApplicabilityStatus.APPLICABLE:
                reasons.append(
                    "Новый authority относится к теме дела, но пока не прошёл applicability gate."
                )
                level = CaseImpactLevel.MEDIUM
                review = True
            else:
                reasons.append(
                    "Новый verified+applicable authority относится к теме активного дела."
                )
                level = CaseImpactLevel.MEDIUM
                review = True

            if freshness_item is not None:
                if freshness_item.status == FreshnessStatus.CURRENT:
                    reasons.append("Это наиболее свежая проверенная позиция в текущей цепочке.")
                    level = CaseImpactLevel.HIGH
                elif freshness_item.status == FreshnessStatus.OLDER_BUT_CONTROLLING:
                    reasons.append("Позиция остаётся контролирующей несмотря на возраст.")
                    if self._rank(level) < self._rank(CaseImpactLevel.HIGH):
                        level = CaseImpactLevel.HIGH
                elif freshness_item.status in {
                    FreshnessStatus.CONFLICTING,
                    FreshnessStatus.SUPERSEDED,
                    FreshnessStatus.LIMITED,
                    FreshnessStatus.REVIEW_REQUIRED,
                }:
                    reasons.append(
                        "Precedent freshness требует отдельной юридической проверки."
                    )
                    level = CaseImpactLevel.CRITICAL
                    review = True

            if authority_id in case.authority_ids_in_use:
                reasons.append(
                    "Authority уже используется в рабочей позиции этого дела и требует повторной проверки."
                )
                level = CaseImpactLevel.CRITICAL
                review = True

            results.append(
                CaseImpactSignal(
                    case_id=case.case_id,
                    authority_id=authority_id,
                    topic=topic,
                    impact_level=level,
                    reasons=tuple(dict.fromkeys(reasons)),
                    requires_lawyer_review=review,
                )
            )
        return tuple(results)

    @staticmethod
    def _rank(level: CaseImpactLevel) -> int:
        return {
            CaseImpactLevel.NONE: 0,
            CaseImpactLevel.LOW: 1,
            CaseImpactLevel.MEDIUM: 2,
            CaseImpactLevel.HIGH: 3,
            CaseImpactLevel.CRITICAL: 4,
        }[level]


class CaseLawIngestionEngine:
    """Ingest verified case law and surface impact on active cases without auto-changing strategy."""

    def __init__(
        self,
        *,
        repository: CaseLawRepository,
        impact_analyzer: CaseImpactAnalyzer | None = None,
    ) -> None:
        self.repository = repository
        self.impact_analyzer = impact_analyzer or CaseImpactAnalyzer()

    def ingest(
        self,
        *,
        record: CaseLawRecord,
        verification: AuthorityVerificationResult,
        applicability: AuthorityApplicabilityResult,
        freshness: PrecedentFreshnessReport | None = None,
        active_cases: tuple[ActiveCaseProfile, ...] = (),
    ) -> CaseLawIngestionResult:
        if verification.status != AuthorityStatus.VERIFIED:
            return CaseLawIngestionResult(
                record=record,
                ingestion_status=IngestionStatus.BLOCKED,
                verification_status=verification.status,
                applicability_status=applicability.status,
                freshness_status=None,
                case_impacts=(),
                requires_human_review=True,
            )

        status = self.repository.upsert(record)
        freshness_status = None
        if freshness is not None:
            freshness_item = next(
                (
                    item
                    for item in freshness.items
                    if item.precedent.authority_id == record.authority_id
                ),
                None,
            )
            if freshness_item is not None:
                freshness_status = freshness_item.status

        impacts = self.impact_analyzer.analyze(
            authority_id=record.authority_id,
            topic=record.topic,
            applicability=applicability,
            freshness=freshness,
            active_cases=active_cases,
        )
        review = (
            applicability.status != ApplicabilityStatus.APPLICABLE
            or freshness_status
            in {
                FreshnessStatus.CONFLICTING,
                FreshnessStatus.SUPERSEDED,
                FreshnessStatus.LIMITED,
                FreshnessStatus.REVIEW_REQUIRED,
            }
            or any(item.requires_lawyer_review for item in impacts)
        )
        return CaseLawIngestionResult(
            record=record,
            ingestion_status=status,
            verification_status=verification.status,
            applicability_status=applicability.status,
            freshness_status=freshness_status,
            case_impacts=impacts,
            requires_human_review=review,
        )

    @staticmethod
    def snapshot(result: CaseLawIngestionResult) -> dict[str, Any]:
        return {
            "record_id": result.record.record_id,
            "authority_id": result.record.authority_id,
            "citation": result.record.citation,
            "topic": result.record.topic,
            "ingestion_status": result.ingestion_status.value,
            "verification_status": result.verification_status.value,
            "applicability_status": result.applicability_status.value,
            "freshness_status": (
                result.freshness_status.value if result.freshness_status else None
            ),
            "case_impacts": [
                {
                    "case_id": item.case_id,
                    "authority_id": item.authority_id,
                    "topic": item.topic,
                    "impact_level": item.impact_level.value,
                    "reasons": list(item.reasons),
                    "requires_lawyer_review": item.requires_lawyer_review,
                }
                for item in result.case_impacts
            ],
            "requires_human_review": result.requires_human_review,
        }
