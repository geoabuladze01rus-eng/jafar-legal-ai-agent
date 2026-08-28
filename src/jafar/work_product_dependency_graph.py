from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .doctrine_case_impact import DoctrineImpactUrgency, WorkProductKind
from .doctrine_evolution import DoctrineEvent, DoctrineEventType, DoctrineEvolutionTimeline


class FragmentKind(StrEnum):
    PARAGRAPH = "paragraph"
    ARGUMENT = "argument"
    REQUEST = "request"
    AUTHORITY_SECTION = "authority_section"
    CONCLUSION = "conclusion"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class WorkProductFragment:
    fragment_id: str
    work_product_id: str
    work_product_kind: WorkProductKind
    fragment_kind: FragmentKind
    ordinal: int
    text: str
    topic: str
    theory_issue_ids: tuple[str, ...] = ()
    authority_ids: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FragmentDependencyImpact:
    fragment_id: str
    work_product_id: str
    doctrine_event_ids: tuple[str, ...]
    matched_authority_ids: tuple[str, ...]
    matched_rule_ids: tuple[str, ...]
    urgency: DoctrineImpactUrgency
    reasons: tuple[str, ...]
    stale: bool
    requires_lawyer_review: bool = True


@dataclass(frozen=True, slots=True)
class WorkProductDependencyReport:
    work_product_id: str
    impacts: tuple[FragmentDependencyImpact, ...]
    stale_fragment_ids: tuple[str, ...]
    critical_fragment_ids: tuple[str, ...]
    requires_lawyer_review: bool


class WorkProductDependencyGraph:
    """Trace doctrine changes to exact fragments of legal work products.

    Dependencies must be explicit. The graph never infers that a paragraph depends on an
    authority merely because similar words appear in both places. It reports stale/review
    signals only from supplied rule, authority, topic or theory-issue links.
    """

    def analyze(
        self,
        *,
        work_product_id: str,
        fragments: tuple[WorkProductFragment, ...],
        doctrine: DoctrineEvolutionTimeline,
    ) -> WorkProductDependencyReport:
        relevant_fragments = tuple(
            fragment for fragment in fragments if fragment.work_product_id == work_product_id
        )
        impacts: list[FragmentDependencyImpact] = []
        for fragment in relevant_fragments:
            events = tuple(
                event
                for event in doctrine.events
                if self._matches(fragment, event, doctrine.legal_issue)
            )
            if not events:
                continue
            urgency, stale, reasons = self._classify(events)
            event_authorities = {
                authority_id
                for event in events
                for authority_id in event.authority_ids
            }
            event_rules = {
                rule_id
                for event in events
                for rule_id in (event.primary_rule_id, event.related_rule_id)
                if rule_id is not None
            }
            impacts.append(
                FragmentDependencyImpact(
                    fragment_id=fragment.fragment_id,
                    work_product_id=fragment.work_product_id,
                    doctrine_event_ids=tuple(event.event_id for event in events),
                    matched_authority_ids=tuple(
                        sorted(event_authorities.intersection(fragment.authority_ids))
                    ),
                    matched_rule_ids=tuple(sorted(event_rules.intersection(fragment.rule_ids))),
                    urgency=urgency,
                    reasons=reasons,
                    stale=stale,
                )
            )

        impacts.sort(
            key=lambda item: (
                -self._urgency_rank(item.urgency),
                self._fragment_ordinal(item.fragment_id, relevant_fragments),
                item.fragment_id,
            )
        )
        stale = tuple(item.fragment_id for item in impacts if item.stale)
        critical = tuple(
            item.fragment_id
            for item in impacts
            if item.urgency == DoctrineImpactUrgency.CRITICAL
        )
        return WorkProductDependencyReport(
            work_product_id=work_product_id,
            impacts=tuple(impacts),
            stale_fragment_ids=stale,
            critical_fragment_ids=critical,
            requires_lawyer_review=bool(impacts),
        )

    @classmethod
    def release_ready(cls, report: WorkProductDependencyReport) -> bool:
        return not any(
            item.stale
            or item.urgency in {DoctrineImpactUrgency.HIGH, DoctrineImpactUrgency.CRITICAL}
            for item in report.impacts
        )

    @classmethod
    def _matches(
        cls,
        fragment: WorkProductFragment,
        event: DoctrineEvent,
        doctrine_issue: str,
    ) -> bool:
        if cls._norm(fragment.topic) == cls._norm(doctrine_issue):
            return True
        if set(fragment.authority_ids).intersection(event.authority_ids):
            return True
        event_rules = {
            rule_id
            for rule_id in (event.primary_rule_id, event.related_rule_id)
            if rule_id is not None
        }
        return bool(set(fragment.rule_ids).intersection(event_rules))

    @classmethod
    def _classify(
        cls,
        events: tuple[DoctrineEvent, ...],
    ) -> tuple[DoctrineImpactUrgency, bool, tuple[str, ...]]:
        types = {event.event_type for event in events}
        reasons: list[str] = []
        stale = False
        if DoctrineEventType.SUPERSESSION in types:
            reasons.append("Фрагмент зависит от правила, которое подтверждённо заменено/преодолено.")
            return DoctrineImpactUrgency.CRITICAL, True, tuple(reasons)
        if DoctrineEventType.CONFLICT in types:
            reasons.append("Фрагмент зависит от правила, по которому имеется подтверждённый конфликт.")
            return DoctrineImpactUrgency.CRITICAL, True, tuple(reasons)
        if DoctrineEventType.EXCEPTION in types:
            reasons.append("Появилось подтверждённое исключение, способное изменить применимость довода.")
            return DoctrineImpactUrgency.HIGH, True, tuple(reasons)
        if DoctrineEventType.NARROWING in types:
            reasons.append("Область применения правила, на котором основан фрагмент, подтверждённо сужена.")
            return DoctrineImpactUrgency.HIGH, True, tuple(reasons)
        if DoctrineEventType.REVIEW_REQUIRED in types:
            reasons.append("По dependency имеется нерешённый doctrinal/freshness сигнал.")
            return DoctrineImpactUrgency.HIGH, False, tuple(reasons)
        if DoctrineEventType.BROADENING in types:
            reasons.append("Правило расширено; фрагмент следует проверить на возможное усиление или изменение аргумента.")
            return DoctrineImpactUrgency.MEDIUM, False, tuple(reasons)
        reasons.append("Связанная доктрина подтверждена без сигнала устаревания фрагмента.")
        return DoctrineImpactUrgency.LOW, stale, tuple(reasons)

    @staticmethod
    def _fragment_ordinal(
        fragment_id: str,
        fragments: tuple[WorkProductFragment, ...],
    ) -> int:
        fragment = next((item for item in fragments if item.fragment_id == fragment_id), None)
        return fragment.ordinal if fragment is not None else 10**9

    @staticmethod
    def _norm(value: str) -> str:
        return " ".join(value.casefold().replace("ё", "е").split())

    @staticmethod
    def _urgency_rank(value: DoctrineImpactUrgency) -> int:
        return {
            DoctrineImpactUrgency.LOW: 1,
            DoctrineImpactUrgency.MEDIUM: 2,
            DoctrineImpactUrgency.HIGH: 3,
            DoctrineImpactUrgency.CRITICAL: 4,
        }[value]
