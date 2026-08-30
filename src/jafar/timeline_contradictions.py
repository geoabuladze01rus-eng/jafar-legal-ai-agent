from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
from typing import Any

from .evidence_graph import CaseEvidenceGraph, EvidenceSource
from .matter_intelligence_writer import MatterIntelligenceWriter, PersistenceOutcome


@dataclass(frozen=True, slots=True)
class TimelineAssertion:
    assertion_id: str
    topic: str
    occurred_at: datetime | None
    earliest_at: datetime | None
    latest_at: datetime | None
    actor: str | None
    evidence_ids: tuple[str, ...]
    statement: str


@dataclass(frozen=True, slots=True)
class TimelineContradiction:
    topic: str
    kind: str
    left_assertion_id: str
    right_assertion_id: str | None
    description: str
    left_sources: tuple[EvidenceSource, ...]
    right_sources: tuple[EvidenceSource, ...]
    severity: str = "high"


class TimelineContradictionAnalyzer:
    """Flag temporal incompatibilities without deciding which chronology is true."""

    def analyze(
        self,
        graph: CaseEvidenceGraph,
        assertions: tuple[TimelineAssertion, ...],
    ) -> tuple[TimelineContradiction, ...]:
        supported = [item for item in assertions if self._sources(graph, item)]
        by_topic: dict[str, list[TimelineAssertion]] = {}
        for item in supported:
            by_topic.setdefault(item.topic, []).append(item)

        result: list[TimelineContradiction] = []
        for topic, items in by_topic.items():
            for left, right in combinations(items, 2):
                contradiction = self._compare_pair(graph, topic, left, right)
                if contradiction is not None:
                    result.append(contradiction)

        for item in supported:
            if item.occurred_at and item.earliest_at and item.occurred_at < item.earliest_at:
                result.append(self._single_bound_conflict(graph, item, "before_earliest"))
            if item.occurred_at and item.latest_at and item.occurred_at > item.latest_at:
                result.append(self._single_bound_conflict(graph, item, "after_latest"))
            if item.earliest_at and item.latest_at and item.earliest_at > item.latest_at:
                result.append(self._single_bound_conflict(graph, item, "invalid_window"))
        return tuple(result)

    def snapshot(
        self,
        graph: CaseEvidenceGraph,
        assertions: tuple[TimelineAssertion, ...],
    ) -> dict[str, Any]:
        items = self.analyze(graph, assertions)
        return {
            "timeline_contradictions": [self._serialize(item) for item in items],
            "requires_human_review": bool(items),
        }

    def persist(self, *, graph: CaseEvidenceGraph, assertions: tuple[TimelineAssertion, ...], writer: MatterIntelligenceWriter, owner_id: str, matter_id: str, analysis_run_id: str) -> PersistenceOutcome:
        items = self.analyze(graph, assertions)
        return writer.write_many(owner_id=owner_id, matter_id=matter_id, kind="contradiction", payloads=[self._serialize(item) | {"statement_a": item.description, "statement_b": item.description, "category": item.kind, "significance": item.severity, "confidence": 0.0, "verification_state": "requires_review", "id": f"timeline:{item.left_assertion_id}:{item.right_assertion_id or item.kind}"} for item in items], analysis_run_id=analysis_run_id)

    def _compare_pair(
        self,
        graph: CaseEvidenceGraph,
        topic: str,
        left: TimelineAssertion,
        right: TimelineAssertion,
    ) -> TimelineContradiction | None:
        left_sources = self._sources(graph, left)
        right_sources = self._sources(graph, right)

        if left.occurred_at and right.occurred_at and left.occurred_at != right.occurred_at:
            return TimelineContradiction(
                topic=topic,
                kind="conflicting_exact_dates",
                left_assertion_id=left.assertion_id,
                right_assertion_id=right.assertion_id,
                description=(
                    f"Для одного события указаны разные даты: "
                    f"{left.occurred_at.isoformat()} и {right.occurred_at.isoformat()}."
                ),
                left_sources=left_sources,
                right_sources=right_sources,
            )

        if self._windows_disjoint(left, right):
            return TimelineContradiction(
                topic=topic,
                kind="disjoint_time_windows",
                left_assertion_id=left.assertion_id,
                right_assertion_id=right.assertion_id,
                description="Источники относят одно событие к несовместимым временным интервалам.",
                left_sources=left_sources,
                right_sources=right_sources,
            )
        return None

    @staticmethod
    def _windows_disjoint(left: TimelineAssertion, right: TimelineAssertion) -> bool:
        left_start = left.earliest_at or left.occurred_at
        left_end = left.latest_at or left.occurred_at
        right_start = right.earliest_at or right.occurred_at
        right_end = right.latest_at or right.occurred_at
        if not all((left_start, left_end, right_start, right_end)):
            return False
        assert left_start and left_end and right_start and right_end
        return left_end < right_start or right_end < left_start

    def _single_bound_conflict(
        self,
        graph: CaseEvidenceGraph,
        item: TimelineAssertion,
        kind: str,
    ) -> TimelineContradiction:
        descriptions = {
            "before_earliest": "Указанная дата события раньше минимально допустимой даты.",
            "after_latest": "Указанная дата события позже максимально допустимой даты.",
            "invalid_window": "Временной интервал некорректен: начало позже окончания.",
        }
        return TimelineContradiction(
            topic=item.topic,
            kind=kind,
            left_assertion_id=item.assertion_id,
            right_assertion_id=None,
            description=descriptions[kind],
            left_sources=self._sources(graph, item),
            right_sources=(),
        )

    @staticmethod
    def _sources(
        graph: CaseEvidenceGraph,
        assertion: TimelineAssertion,
    ) -> tuple[EvidenceSource, ...]:
        if not assertion.evidence_ids:
            return ()
        sources = tuple(graph.source(evidence_id) for evidence_id in assertion.evidence_ids)
        if any(source is None for source in sources):
            return ()
        return tuple(source for source in sources if source is not None)

    @staticmethod
    def _serialize(item: TimelineContradiction) -> dict[str, Any]:
        def source_ref(source: EvidenceSource) -> dict[str, Any]:
            return {
                "evidence_id": source.evidence_id,
                "document_name": source.document_name,
                "page": source.page,
                "chunk_index": source.metadata.get("chunk_index"),
                "actor": source.actor,
                "event_id": source.event_id,
                "excerpt": source.excerpt,
            }

        return {
            "topic": item.topic,
            "kind": item.kind,
            "left_assertion_id": item.left_assertion_id,
            "right_assertion_id": item.right_assertion_id,
            "description": item.description,
            "left_sources": [source_ref(source) for source in item.left_sources],
            "right_sources": [source_ref(source) for source in item.right_sources],
            "severity": item.severity,
        }
