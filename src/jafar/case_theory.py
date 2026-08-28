from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .cross_document_contradictions import CrossDocumentContradiction
from .evidence_graph import CaseEvidenceGraph, EvidenceClaim, EvidenceSource
from .timeline_contradictions import TimelineContradiction


class TheoryStatus(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True, slots=True)
class CaseTheoryIssue:
    issue_id: str
    topic: str
    statement: str
    position: str
    status: TheoryStatus
    claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    source_refs: tuple[dict[str, Any], ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CaseTheoryReport:
    issues: tuple[CaseTheoryIssue, ...]
    supported_count: int
    contradicted_count: int
    unsupported_count: int
    review_required_count: int
    requires_human_review: bool


class CaseTheoryEngine:
    """Build a source-traceable theory map without deciding ultimate legal truth."""

    def build(
        self,
        *,
        graph: CaseEvidenceGraph,
        cross_document: tuple[CrossDocumentContradiction, ...] = (),
        timeline: tuple[TimelineContradiction, ...] = (),
    ) -> CaseTheoryReport:
        cross_by_claim: dict[str, list[CrossDocumentContradiction]] = {}
        for item in cross_document:
            cross_by_claim.setdefault(item.left_claim_id, []).append(item)
            cross_by_claim.setdefault(item.right_claim_id, []).append(item)

        timeline_evidence_ids: set[str] = set()
        for item in timeline:
            timeline_evidence_ids.update(source.evidence_id for source in item.left_sources)
            timeline_evidence_ids.update(source.evidence_id for source in item.right_sources)

        issues: list[CaseTheoryIssue] = []
        for claim in graph.claims():
            reasons: list[str] = []
            status = TheoryStatus.SUPPORTED

            if not claim.supported:
                status = TheoryStatus.UNSUPPORTED
                reasons.append("Утверждение не подтверждено валидной ссылкой на источник.")

            contradictions = cross_by_claim.get(claim.claim_id, [])
            if contradictions:
                status = TheoryStatus.CONTRADICTED
                reasons.append(
                    "Есть поддержанное источниками противоречащее утверждение по той же теме."
                )

            if claim.evidence_ids and any(
                item in timeline_evidence_ids for item in claim.evidence_ids
            ):
                status = TheoryStatus.REVIEW_REQUIRED
                reasons.append("Источник связан с обнаруженным временным противоречием.")

            refs = self._source_refs(graph, claim)
            issues.append(
                CaseTheoryIssue(
                    issue_id=f"theory:{claim.claim_id}",
                    topic=claim.topic,
                    statement=claim.statement,
                    position=claim.position,
                    status=status,
                    claim_ids=(claim.claim_id,),
                    evidence_ids=claim.evidence_ids,
                    source_refs=refs,
                    reasons=tuple(reasons),
                )
            )

        supported_count = sum(item.status == TheoryStatus.SUPPORTED for item in issues)
        contradicted_count = sum(item.status == TheoryStatus.CONTRADICTED for item in issues)
        unsupported_count = sum(item.status == TheoryStatus.UNSUPPORTED for item in issues)
        review_required_count = sum(
            item.status == TheoryStatus.REVIEW_REQUIRED for item in issues
        )
        requires_human_review = any(
            item.status
            in {
                TheoryStatus.CONTRADICTED,
                TheoryStatus.UNSUPPORTED,
                TheoryStatus.REVIEW_REQUIRED,
            }
            for item in issues
        )

        return CaseTheoryReport(
            issues=tuple(issues),
            supported_count=supported_count,
            contradicted_count=contradicted_count,
            unsupported_count=unsupported_count,
            review_required_count=review_required_count,
            requires_human_review=requires_human_review,
        )

    def snapshot(self, report: CaseTheoryReport) -> dict[str, Any]:
        return {
            "issues": [
                {
                    "issue_id": item.issue_id,
                    "topic": item.topic,
                    "statement": item.statement,
                    "position": item.position,
                    "status": item.status.value,
                    "claim_ids": list(item.claim_ids),
                    "evidence_ids": list(item.evidence_ids),
                    "source_refs": list(item.source_refs),
                    "reasons": list(item.reasons),
                }
                for item in report.issues
            ],
            "counts": {
                "supported": report.supported_count,
                "contradicted": report.contradicted_count,
                "unsupported": report.unsupported_count,
                "review_required": report.review_required_count,
            },
            "requires_human_review": report.requires_human_review,
        }

    @staticmethod
    def _source_refs(
        graph: CaseEvidenceGraph,
        claim: EvidenceClaim,
    ) -> tuple[dict[str, Any], ...]:
        refs: list[dict[str, Any]] = []
        for evidence_id in claim.evidence_ids:
            source = graph.source(evidence_id)
            if source is None:
                continue
            refs.append(CaseTheoryEngine._source_ref(source))
        return tuple(refs)

    @staticmethod
    def _source_ref(source: EvidenceSource) -> dict[str, Any]:
        return {
            "evidence_id": source.evidence_id,
            "document_name": source.document_name,
            "document_fingerprint": source.document_fingerprint,
            "page": source.page,
            "chunk_index": source.metadata.get("chunk_index"),
            "actor": source.actor,
            "event_id": source.event_id,
            "excerpt": source.excerpt,
        }
