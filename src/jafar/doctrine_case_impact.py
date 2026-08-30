from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .case_theory import CaseTheoryReport
from .doctrine_evolution import DoctrineEventType, DoctrineEvolutionTimeline


class DoctrineImpactUrgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkProductKind(StrEnum):
    THEORY = "theory"
    MOTION = "motion"
    COMPLAINT = "complaint"
    COURT_SPEECH = "court_speech"
    INTERROGATION_PLAN = "interrogation_plan"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ActiveWorkProduct:
    work_product_id: str
    kind: WorkProductKind
    title: str
    topic: str
    authority_ids: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DoctrineCaseImpact:
    issue_id: str
    topic: str
    doctrine_event_ids: tuple[str, ...]
    affected_work_product_ids: tuple[str, ...]
    urgency: DoctrineImpactUrgency
    reasons: tuple[str, ...]
    requires_lawyer_review: bool = True


@dataclass(frozen=True, slots=True)
class DoctrineCaseImpactReport:
    case_id: str
    impacts: tuple[DoctrineCaseImpact, ...]
    critical_issue_ids: tuple[str, ...]
    requires_lawyer_review: bool


class DoctrineToCaseImpactEngine:
    """Map verified doctrine changes to concrete active case issues and work products.

    The engine never rewrites a legal position. It only identifies which existing theory
    issues or work products should be reviewed because a verified doctrine event touches
    their topic, authority or normalized rule.
    """

    def analyze(
        self,
        *,
        case_id: str,
        theory: CaseTheoryReport,
        doctrine: DoctrineEvolutionTimeline,
        work_products: tuple[ActiveWorkProduct, ...] = (),
    ) -> DoctrineCaseImpactReport:
        doctrine_topic = self._norm(doctrine.legal_issue)
        impacts: list[DoctrineCaseImpact] = []

        for issue in theory.issues:
            if self._norm(issue.topic) != doctrine_topic:
                continue

            related_events = tuple(doctrine.events)
            related_products = tuple(
                product
                for product in work_products
                if self._product_matches(product, issue.topic, related_events)
            )
            urgency, reasons = self._classify(related_events, related_products)
            impacts.append(
                DoctrineCaseImpact(
                    issue_id=issue.issue_id,
                    topic=issue.topic,
                    doctrine_event_ids=tuple(event.event_id for event in related_events),
                    affected_work_product_ids=tuple(
                        product.work_product_id for product in related_products
                    ),
                    urgency=urgency,
                    reasons=reasons,
                )
            )

        impacts.sort(
            key=lambda item: (
                -self._urgency_rank(item.urgency),
                item.issue_id,
            )
        )
        critical = tuple(
            item.issue_id
            for item in impacts
            if item.urgency == DoctrineImpactUrgency.CRITICAL
        )
        return DoctrineCaseImpactReport(
            case_id=case_id,
            impacts=tuple(impacts),
            critical_issue_ids=critical,
            requires_lawyer_review=bool(impacts),
        )

    @classmethod
    def release_ready(cls, report: DoctrineCaseImpactReport) -> bool:
        return not any(
            item.urgency in {DoctrineImpactUrgency.HIGH, DoctrineImpactUrgency.CRITICAL}
            for item in report.impacts
        )

    @classmethod
    def _classify(
        cls,
        events: tuple,
        products: tuple[ActiveWorkProduct, ...],
    ) -> tuple[DoctrineImpactUrgency, tuple[str, ...]]:
        reasons: list[str] = []
        event_types = {event.event_type for event in events}

        if DoctrineEventType.CONFLICT in event_types:
            reasons.append("В релевантной доктрине имеется подтверждённый конфликт.")
            urgency = DoctrineImpactUrgency.CRITICAL
        elif DoctrineEventType.SUPERSESSION in event_types:
            reasons.append("Релевантное правило подтверждённо заменено/преодолено.")
            urgency = DoctrineImpactUrgency.CRITICAL
        elif DoctrineEventType.EXCEPTION in event_types:
            reasons.append("Появилось подтверждённое исключение из применяемого правила.")
            urgency = DoctrineImpactUrgency.HIGH
        elif DoctrineEventType.NARROWING in event_types:
            reasons.append("Область применения релевантного правила подтверждённо сужена.")
            urgency = DoctrineImpactUrgency.HIGH
        elif DoctrineEventType.BROADENING in event_types:
            reasons.append("Область применения релевантного правила подтверждённо расширена.")
            urgency = DoctrineImpactUrgency.MEDIUM
        elif DoctrineEventType.REVIEW_REQUIRED in event_types:
            reasons.append("По доктрине остаётся нерешённый freshness/review сигнал.")
            urgency = DoctrineImpactUrgency.HIGH
        else:
            reasons.append("Доктрина подтверждена/развивается без критического сигнала.")
            urgency = DoctrineImpactUrgency.LOW

        if products:
            reasons.append("Изменение затрагивает уже подготовленный рабочий продукт по делу.")
            if urgency == DoctrineImpactUrgency.LOW:
                urgency = DoctrineImpactUrgency.MEDIUM
            elif urgency == DoctrineImpactUrgency.MEDIUM:
                urgency = DoctrineImpactUrgency.HIGH
            elif urgency == DoctrineImpactUrgency.HIGH:
                urgency = DoctrineImpactUrgency.CRITICAL

        return urgency, tuple(dict.fromkeys(reasons))

    @classmethod
    def _product_matches(cls, product: ActiveWorkProduct, topic: str, events: tuple) -> bool:
        if cls._norm(product.topic) == cls._norm(topic):
            return True
        authority_ids = {
            authority_id
            for event in events
            for authority_id in event.authority_ids
        }
        rule_ids = {
            rule_id
            for event in events
            for rule_id in (event.primary_rule_id, event.related_rule_id)
            if rule_id is not None
        }
        return bool(
            authority_ids.intersection(product.authority_ids)
            or rule_ids.intersection(product.rule_ids)
        )

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
