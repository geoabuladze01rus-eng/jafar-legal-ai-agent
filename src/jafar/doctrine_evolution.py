from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from .legal_rule_conflict_graph import (
    LegalRuleConflictReport,
    RuleConflictEdge,
    RuleRelationType,
)
from .precedent_freshness import FreshnessStatus, PrecedentFreshnessReport


class DoctrineEventType(StrEnum):
    ORIGIN = "origin"
    CONFIRMATION = "confirmation"
    NARROWING = "narrowing"
    BROADENING = "broadening"
    EXCEPTION = "exception"
    CONFLICT = "conflict"
    SUPERSESSION = "supersession"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True, slots=True)
class DoctrineEvent:
    event_id: str
    occurred_on: date | None
    event_type: DoctrineEventType
    legal_issue: str
    primary_rule_id: str
    related_rule_id: str | None
    authority_ids: tuple[str, ...]
    summary: str
    verified: bool
    requires_lawyer_review: bool


@dataclass(frozen=True, slots=True)
class DoctrineEvolutionTimeline:
    legal_issue: str
    events: tuple[DoctrineEvent, ...]
    current_rule_ids: tuple[str, ...]
    unresolved_rule_pairs: tuple[tuple[str, str], ...]
    precedent_requires_review: bool
    requires_lawyer_review: bool


class DoctrineEvolutionEngine:
    """Combine rule relationships and precedent freshness into an auditable doctrine timeline.

    The engine does not infer missing treatment. Rule relationships must already be verified
    by the conflict graph, while chronology dates come from verified precedent records.
    """

    def build(
        self,
        *,
        rule_graph: LegalRuleConflictReport,
        precedent: PrecedentFreshnessReport | None = None,
    ) -> DoctrineEvolutionTimeline:
        authority_dates = self._authority_dates(precedent)
        events: list[DoctrineEvent] = []

        for rule in rule_graph.rules:
            events.append(
                DoctrineEvent(
                    event_id=f"doctrine:origin:{rule.rule_id}",
                    occurred_on=authority_dates.get(rule.authority_id),
                    event_type=DoctrineEventType.ORIGIN,
                    legal_issue=rule_graph.legal_issue,
                    primary_rule_id=rule.rule_id,
                    related_rule_id=None,
                    authority_ids=(rule.authority_id,),
                    summary="Зафиксировано нормализованное правило из проверенного holding.",
                    verified=True,
                    requires_lawyer_review=True,
                )
            )

        for edge in rule_graph.edges:
            events.append(self._event_from_edge(edge, rule_graph.legal_issue, authority_dates))

        if precedent is not None:
            for item in precedent.items:
                if item.status in {
                    FreshnessStatus.CONFLICTING,
                    FreshnessStatus.SUPERSEDED,
                    FreshnessStatus.LIMITED,
                    FreshnessStatus.REVIEW_REQUIRED,
                }:
                    matching_rules = tuple(
                        rule.rule_id
                        for rule in rule_graph.rules
                        if rule.authority_id == item.precedent.authority_id
                    )
                    for rule_id in matching_rules:
                        events.append(
                            DoctrineEvent(
                                event_id=f"doctrine:freshness:{rule_id}:{item.status.value}",
                                occurred_on=item.precedent.decided_on,
                                event_type=DoctrineEventType.REVIEW_REQUIRED,
                                legal_issue=rule_graph.legal_issue,
                                primary_rule_id=rule_id,
                                related_rule_id=None,
                                authority_ids=(item.precedent.authority_id,),
                                summary="Precedent freshness содержит сигнал, требующий отдельной юридической проверки.",
                                verified=True,
                                requires_lawyer_review=True,
                            )
                        )

        events.sort(
            key=lambda event: (
                event.occurred_on is None,
                event.occurred_on or date.max,
                event.event_type.value,
                event.event_id,
            )
        )

        superseded = {
            edge.left.rule_id
            for edge in rule_graph.edges
            if edge.verified and edge.relation == RuleRelationType.SUPERSEDED
        }
        current_rule_ids = tuple(
            rule.rule_id for rule in rule_graph.rules if rule.rule_id not in superseded
        )
        review = (
            rule_graph.requires_human_review
            or bool(rule_graph.unresolved_pairs)
            or (precedent.requires_human_review if precedent is not None else False)
            or any(event.requires_lawyer_review for event in events)
        )
        return DoctrineEvolutionTimeline(
            legal_issue=rule_graph.legal_issue,
            events=tuple(events),
            current_rule_ids=current_rule_ids,
            unresolved_rule_pairs=rule_graph.unresolved_pairs,
            precedent_requires_review=(precedent.requires_human_review if precedent is not None else False),
            requires_lawyer_review=review,
        )

    @staticmethod
    def release_ready(timeline: DoctrineEvolutionTimeline) -> bool:
        if timeline.unresolved_rule_pairs or timeline.precedent_requires_review:
            return False
        return not any(
            event.event_type in {DoctrineEventType.CONFLICT, DoctrineEventType.SUPERSESSION}
            for event in timeline.events
        )

    @staticmethod
    def _authority_dates(precedent: PrecedentFreshnessReport | None) -> dict[str, date]:
        if precedent is None:
            return {}
        return {
            item.precedent.authority_id: item.precedent.decided_on
            for item in precedent.items
        }

    @staticmethod
    def _event_from_edge(
        edge: RuleConflictEdge,
        legal_issue: str,
        authority_dates: dict[str, date],
    ) -> DoctrineEvent:
        event_type = {
            RuleRelationType.SAME_RULE: DoctrineEventType.CONFIRMATION,
            RuleRelationType.NARROWER: DoctrineEventType.NARROWING,
            RuleRelationType.BROADER: DoctrineEventType.BROADENING,
            RuleRelationType.EXCEPTION: DoctrineEventType.EXCEPTION,
            RuleRelationType.CONFLICT: DoctrineEventType.CONFLICT,
            RuleRelationType.SUPERSEDED: DoctrineEventType.SUPERSESSION,
            RuleRelationType.UNKNOWN: DoctrineEventType.REVIEW_REQUIRED,
        }[edge.relation]
        dates = [
            value
            for value in (
                authority_dates.get(edge.left.authority_id),
                authority_dates.get(edge.right.authority_id),
            )
            if value is not None
        ]
        occurred_on = max(dates) if dates else None
        return DoctrineEvent(
            event_id=f"doctrine:{event_type.value}:{edge.left.rule_id}:{edge.right.rule_id}",
            occurred_on=occurred_on,
            event_type=event_type,
            legal_issue=legal_issue,
            primary_rule_id=edge.left.rule_id,
            related_rule_id=edge.right.rule_id,
            authority_ids=tuple(dict.fromkeys((edge.left.authority_id, edge.right.authority_id))),
            summary=edge.explanation,
            verified=edge.verified,
            requires_lawyer_review=event_type in {
                DoctrineEventType.NARROWING,
                DoctrineEventType.BROADENING,
                DoctrineEventType.EXCEPTION,
                DoctrineEventType.CONFLICT,
                DoctrineEventType.SUPERSESSION,
                DoctrineEventType.REVIEW_REQUIRED,
            },
        )
