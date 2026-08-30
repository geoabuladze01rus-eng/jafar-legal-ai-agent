from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, ClassVar

from .evidence_graph import CaseEvidenceGraph, EvidenceClaim, EvidenceSource
from .matter_intelligence_writer import MatterIntelligenceWriter, PersistenceOutcome


@dataclass(frozen=True, slots=True)
class CrossDocumentContradiction:
    topic: str
    left_claim_id: str
    right_claim_id: str
    left_statement: str
    right_statement: str
    left_position: str
    right_position: str
    left_sources: tuple[EvidenceSource, ...]
    right_sources: tuple[EvidenceSource, ...]
    cross_document: bool
    cross_actor: bool
    severity: str = "high"


class CrossDocumentContradictionGraph:
    """Detect conflicts between supported claims and preserve both source trails."""

    OPPOSING_POSITIONS: ClassVar[set[tuple[str, str]]] = {
        ("supports", "opposes"),
        ("opposes", "supports"),
        ("yes", "no"),
        ("no", "yes"),
        ("present", "absent"),
        ("absent", "present"),
        ("occurred", "did_not_occur"),
        ("did_not_occur", "occurred"),
    }

    def build(self, graph: CaseEvidenceGraph) -> tuple[CrossDocumentContradiction, ...]:
        claims = [claim for claim in graph.claims() if claim.supported]
        by_topic: dict[str, list[EvidenceClaim]] = {}
        for claim in claims:
            by_topic.setdefault(claim.topic, []).append(claim)

        contradictions: list[CrossDocumentContradiction] = []
        for topic, topic_claims in by_topic.items():
            for left, right in combinations(topic_claims, 2):
                if not self._conflicts(left, right):
                    continue
                left_sources = self._sources(graph, left)
                right_sources = self._sources(graph, right)
                if not left_sources or not right_sources:
                    continue
                left_documents = {source.document_fingerprint for source in left_sources}
                right_documents = {source.document_fingerprint for source in right_sources}
                left_actors = {source.actor for source in left_sources if source.actor}
                right_actors = {source.actor for source in right_sources if source.actor}
                contradictions.append(
                    CrossDocumentContradiction(
                        topic=topic,
                        left_claim_id=left.claim_id,
                        right_claim_id=right.claim_id,
                        left_statement=left.statement,
                        right_statement=right.statement,
                        left_position=left.position,
                        right_position=right.position,
                        left_sources=left_sources,
                        right_sources=right_sources,
                        cross_document=left_documents != right_documents,
                        cross_actor=bool(left_actors and right_actors and left_actors != right_actors),
                    )
                )
        return tuple(contradictions)

    def snapshot(self, graph: CaseEvidenceGraph) -> dict[str, Any]:
        items = self.build(graph)
        return {
            "contradictions": [self._serialize(item) for item in items],
            "requires_human_review": bool(items),
        }

    def persist(self, *, graph: CaseEvidenceGraph, writer: MatterIntelligenceWriter, owner_id: str, matter_id: str, analysis_run_id: str) -> PersistenceOutcome:
        items = self.build(graph)
        return writer.write_many(owner_id=owner_id, matter_id=matter_id, kind="contradiction", payloads=[self._serialize(item) | {"statement_a": item.left_statement, "statement_b": item.right_statement, "source_a": item.left_sources[0].evidence_id if item.left_sources else None, "source_b": item.right_sources[0].evidence_id if item.right_sources else None, "category": "cross_document" if item.cross_document else "cross_claim", "significance": item.severity, "confidence": 0.0, "verification_state": "requires_review", "id": f"cross:{item.left_claim_id}:{item.right_claim_id}"} for item in items], analysis_run_id=analysis_run_id)

    def _conflicts(self, left: EvidenceClaim, right: EvidenceClaim) -> bool:
        if left.statement.strip().casefold() == right.statement.strip().casefold():
            return False
        positions = (left.position.strip().casefold(), right.position.strip().casefold())
        if positions in self.OPPOSING_POSITIONS:
            return True
        return positions[0] != positions[1] and "uncertain" not in positions

    @staticmethod
    def _sources(graph: CaseEvidenceGraph, claim: EvidenceClaim) -> tuple[EvidenceSource, ...]:
        return tuple(
            source
            for evidence_id in claim.evidence_ids
            if (source := graph.source(evidence_id)) is not None
        )

    @staticmethod
    def _serialize(item: CrossDocumentContradiction) -> dict[str, Any]:
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
            "left_claim_id": item.left_claim_id,
            "right_claim_id": item.right_claim_id,
            "left_statement": item.left_statement,
            "right_statement": item.right_statement,
            "left_position": item.left_position,
            "right_position": item.right_position,
            "left_sources": [source_ref(source) for source in item.left_sources],
            "right_sources": [source_ref(source) for source in item.right_sources],
            "cross_document": item.cross_document,
            "cross_actor": item.cross_actor,
            "severity": item.severity,
        }
