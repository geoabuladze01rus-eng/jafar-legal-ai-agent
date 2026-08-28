from datetime import datetime, timezone

from jafar.case_theory import CaseTheoryEngine, TheoryStatus
from jafar.cross_document_contradictions import CrossDocumentContradictionGraph
from jafar.evidence_graph import CaseEvidenceGraph, EvidenceSource
from jafar.timeline_contradictions import TimelineAssertion, TimelineContradictionAnalyzer


def source(evidence_id: str, document: str, page: int, actor: str) -> EvidenceSource:
    return EvidenceSource(
        evidence_id=evidence_id,
        document_name=document,
        document_fingerprint=document,
        excerpt=f"excerpt from {document}",
        page=page,
        actor=actor,
        metadata={"chunk_index": 1},
    )


def test_supported_claim_remains_supported() -> None:
    graph = CaseEvidenceGraph()
    graph.add_source(source("e1", "doc1", 1, "witness"))
    graph.add_claim(
        claim_id="c1",
        topic="presence",
        statement="Свидетель находился на месте.",
        position="present",
        provider="openai",
        evidence_ids=("e1",),
    )

    report = CaseTheoryEngine().build(graph=graph)

    assert report.issues[0].status == TheoryStatus.SUPPORTED
    assert report.supported_count == 1
    assert report.requires_human_review is False


def test_cross_document_conflict_marks_claims_contradicted() -> None:
    graph = CaseEvidenceGraph()
    graph.add_source(source("e1", "interview-1", 2, "witness"))
    graph.add_source(source("e2", "interview-2", 8, "witness"))
    graph.add_claim(
        claim_id="c1",
        topic="presence",
        statement="Свидетель был на месте.",
        position="present",
        provider="openai",
        evidence_ids=("e1",),
    )
    graph.add_claim(
        claim_id="c2",
        topic="presence",
        statement="Свидетель отсутствовал.",
        position="absent",
        provider="qwen",
        evidence_ids=("e2",),
    )
    contradictions = CrossDocumentContradictionGraph().build(graph)

    report = CaseTheoryEngine().build(graph=graph, cross_document=contradictions)

    assert {item.status for item in report.issues} == {TheoryStatus.CONTRADICTED}
    assert report.contradicted_count == 2
    assert report.requires_human_review is True


def test_unsupported_claim_is_not_promoted_to_theory_fact() -> None:
    graph = CaseEvidenceGraph()
    graph.add_claim(
        claim_id="c1",
        topic="payment",
        statement="Деньги были переданы.",
        position="occurred",
        provider="kimi",
        evidence_ids=("missing-evidence",),
    )

    report = CaseTheoryEngine().build(graph=graph)

    assert report.issues[0].status == TheoryStatus.UNSUPPORTED
    assert report.unsupported_count == 1


def test_timeline_conflict_requires_review_and_keeps_source_trace() -> None:
    graph = CaseEvidenceGraph()
    graph.add_source(source("e1", "protocol-1", 4, "witness"))
    graph.add_source(source("e2", "protocol-2", 9, "investigator"))
    graph.add_claim(
        claim_id="c1",
        topic="meeting",
        statement="Встреча состоялась.",
        position="occurred",
        provider="openai",
        evidence_ids=("e1",),
    )
    assertions = (
        TimelineAssertion(
            assertion_id="t1",
            topic="meeting",
            occurred_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
            earliest_at=None,
            latest_at=None,
            actor="witness",
            evidence_ids=("e1",),
            statement="Встреча была 12 августа.",
        ),
        TimelineAssertion(
            assertion_id="t2",
            topic="meeting",
            occurred_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
            earliest_at=None,
            latest_at=None,
            actor="investigator",
            evidence_ids=("e2",),
            statement="Встреча была 14 августа.",
        ),
    )
    timeline = TimelineContradictionAnalyzer().analyze(graph, assertions)

    report = CaseTheoryEngine().build(graph=graph, timeline=timeline)
    issue = report.issues[0]

    assert issue.status == TheoryStatus.REVIEW_REQUIRED
    assert issue.source_refs[0]["document_name"] == "protocol-1"
    assert issue.source_refs[0]["page"] == 4
    assert report.review_required_count == 1


def test_snapshot_exposes_counts_and_reasons() -> None:
    graph = CaseEvidenceGraph()
    graph.add_source(source("e1", "doc", 3, "expert"))
    graph.add_claim(
        claim_id="c1",
        topic="amount",
        statement="Сумма подтверждается расчётом.",
        position="supports",
        provider="openai",
        evidence_ids=("e1",),
    )
    engine = CaseTheoryEngine()
    report = engine.build(graph=graph)
    snapshot = engine.snapshot(report)

    assert snapshot["counts"]["supported"] == 1
    assert snapshot["issues"][0]["source_refs"][0]["page"] == 3
