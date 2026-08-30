from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from itertools import combinations
from typing import ClassVar

from .authority_applicability import AuthorityWeight


class PrecedentTreatment(StrEnum):
    CONSISTENT = "consistent"
    CONFLICTING = "conflicting"
    LIMITING = "limiting"
    EXPANDING = "expanding"
    SUPERSEDING = "superseding"
    UNKNOWN = "unknown"


class FreshnessStatus(StrEnum):
    CURRENT = "current"
    OLDER_BUT_CONTROLLING = "older_but_controlling"
    LIMITED = "limited"
    SUPERSEDED = "superseded"
    CONFLICTING = "conflicting"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True, slots=True)
class PrecedentRecord:
    authority_id: str
    citation: str
    topic: str
    proposition: str
    decided_on: date
    weight: AuthorityWeight
    authority_type: str
    source_url: str
    source_fingerprint: str


@dataclass(frozen=True, slots=True)
class PrecedentRelation:
    earlier_id: str
    later_id: str
    treatment: PrecedentTreatment
    explanation: str
    verified: bool = False


@dataclass(frozen=True, slots=True)
class PrecedentFreshnessItem:
    precedent: PrecedentRecord
    status: FreshnessStatus
    freshness_rank: int
    reasons: tuple[str, ...]
    later_relations: tuple[PrecedentRelation, ...]


@dataclass(frozen=True, slots=True)
class PrecedentFreshnessReport:
    topic: str
    chronology: tuple[PrecedentRecord, ...]
    items: tuple[PrecedentFreshnessItem, ...]
    conflicts: tuple[PrecedentRelation, ...]
    requires_human_review: bool


class PrecedentFreshnessEngine:
    """Build a chronology of verified precedent relationships without treating recency as authority.

    A later case is not automatically stronger. Rank combines explicit authority weight,
    chronology and only *verified* treatment relationships supplied by a canonical resolver.
    """

    WEIGHT_SCORE: ClassVar[dict[AuthorityWeight, int]] = {
        AuthorityWeight.BINDING: 500,
        AuthorityWeight.HIGH: 400,
        AuthorityWeight.PERSUASIVE: 250,
        AuthorityWeight.CONTEXTUAL: 100,
        AuthorityWeight.UNKNOWN: 0,
    }

    def build(
        self,
        *,
        topic: str,
        precedents: tuple[PrecedentRecord, ...],
        relations: tuple[PrecedentRelation, ...] = (),
    ) -> PrecedentFreshnessReport:
        normalized = topic.strip().casefold()
        relevant = tuple(
            sorted(
                (item for item in precedents if item.topic.strip().casefold() == normalized),
                key=lambda item: (item.decided_on, item.authority_id),
            )
        )
        ids = {item.authority_id for item in relevant}
        verified_relations = tuple(
            relation
            for relation in relations
            if relation.verified and relation.earlier_id in ids and relation.later_id in ids
        )
        by_earlier: dict[str, list[PrecedentRelation]] = {}
        for relation in verified_relations:
            by_earlier.setdefault(relation.earlier_id, []).append(relation)

        latest_date = max((item.decided_on for item in relevant), default=None)
        items: list[PrecedentFreshnessItem] = []
        for precedent in relevant:
            later = tuple(
                sorted(
                    by_earlier.get(precedent.authority_id, ()),
                    key=lambda relation: relation.later_id,
                )
            )
            status, reasons = self._status(precedent, later, latest_date)
            items.append(
                PrecedentFreshnessItem(
                    precedent=precedent,
                    status=status,
                    freshness_rank=self._rank(precedent, status, latest_date),
                    reasons=reasons,
                    later_relations=later,
                )
            )

        items.sort(key=lambda item: (-item.freshness_rank, item.precedent.authority_id))
        conflicts = tuple(
            relation
            for relation in verified_relations
            if relation.treatment == PrecedentTreatment.CONFLICTING
        )
        review = bool(conflicts) or any(
            item.status in {FreshnessStatus.CONFLICTING, FreshnessStatus.REVIEW_REQUIRED}
            for item in items
        )
        return PrecedentFreshnessReport(
            topic=topic,
            chronology=relevant,
            items=tuple(items),
            conflicts=conflicts,
            requires_human_review=review,
        )

    def detect_unresolved_pairs(
        self,
        *,
        topic: str,
        precedents: tuple[PrecedentRecord, ...],
        relations: tuple[PrecedentRelation, ...],
    ) -> tuple[tuple[str, str], ...]:
        normalized = topic.strip().casefold()
        relevant = [item for item in precedents if item.topic.strip().casefold() == normalized]
        known = {
            frozenset((relation.earlier_id, relation.later_id))
            for relation in relations
            if relation.verified
        }
        return tuple(
            (left.authority_id, right.authority_id)
            for left, right in combinations(relevant, 2)
            if frozenset((left.authority_id, right.authority_id)) not in known
            and left.proposition.strip().casefold() != right.proposition.strip().casefold()
        )

    @classmethod
    def _rank(
        cls,
        precedent: PrecedentRecord,
        status: FreshnessStatus,
        latest_date: date | None,
    ) -> int:
        score = cls.WEIGHT_SCORE[precedent.weight]
        if latest_date is not None:
            age_days = max(0, (latest_date - precedent.decided_on).days)
            score += max(0, 120 - min(120, age_days // 30))
        if status == FreshnessStatus.CURRENT:
            score += 80
        elif status == FreshnessStatus.OLDER_BUT_CONTROLLING:
            score += 100
        elif status == FreshnessStatus.LIMITED:
            score -= 60
        elif status == FreshnessStatus.SUPERSEDED:
            score -= 200
        elif status == FreshnessStatus.CONFLICTING:
            score -= 80
        return score

    @staticmethod
    def _status(
        precedent: PrecedentRecord,
        later: tuple[PrecedentRelation, ...],
        latest_date: date | None,
    ) -> tuple[FreshnessStatus, tuple[str, ...]]:
        treatments = {item.treatment for item in later}
        reasons: list[str] = []
        if PrecedentTreatment.SUPERSEDING in treatments:
            reasons.append("Более поздний проверенный источник прямо заменяет/преодолевает эту позицию.")
            return FreshnessStatus.SUPERSEDED, tuple(reasons)
        if PrecedentTreatment.CONFLICTING in treatments:
            reasons.append("Есть более поздняя проверенная конфликтующая позиция по той же теме.")
            return FreshnessStatus.CONFLICTING, tuple(reasons)
        if PrecedentTreatment.LIMITING in treatments:
            reasons.append("Последующая практика ограничивает область применения позиции.")
            return FreshnessStatus.LIMITED, tuple(reasons)
        if later and all(item.treatment in {PrecedentTreatment.CONSISTENT, PrecedentTreatment.EXPANDING} for item in later):
            reasons.append("Последующая проверенная практика не отменяет позицию и подтверждает/развивает её.")
            if precedent.weight == AuthorityWeight.BINDING:
                return FreshnessStatus.OLDER_BUT_CONTROLLING, tuple(reasons)
        if latest_date == precedent.decided_on:
            reasons.append("Это наиболее свежая проверенная позиция в текущей подборке, но свежесть сама по себе не определяет её силу.")
            return FreshnessStatus.CURRENT, tuple(reasons)
        reasons.append("Нет проверенного последующего treatment; требуется юридическая проверка перед выводом об актуальности.")
        return FreshnessStatus.REVIEW_REQUIRED, tuple(reasons)
