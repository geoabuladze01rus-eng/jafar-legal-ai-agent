from jafar.cross_document_contradictions import CrossDocumentContradictionGraph
from jafar.evidence_graph import CaseEvidenceGraph, EvidenceSource


def test_detects_cross_document_conflict_with_source_trails() -> None:
    graph = CaseEvidenceGraph()
    left = EvidenceSource(
        evidence_id="doc:a:page:2:chunk:1",
        document_name="interview-1.pdf",
        document_fingerprint="a",
        excerpt="Свидетель видел автомобиль в 20:00.",
        page=2,
        actor="Свидетель Петров",
        event_id="interview-1",
        metadata={"chunk_index": 1},
    )
    right = EvidenceSource(
        evidence_id="doc:b:page:7:chunk:2",
        document_name="interview-2.pdf",
        document_fingerprint="b",
        excerpt="Свидетель не видел автомобиль в этот вечер.",
        page=7,
        actor="Свидетель Петров",
        event_id="interview-2",
        metadata={"chunk_index": 2},
    )
    graph.add_source(left)
    graph.add_source(right)
    graph.add_claim(
        claim_id="claim-1",
        topic="vehicle_seen",
        statement="Автомобиль был замечен свидетелем вечером.",
        position="yes",
        provider="openai",
        evidence_ids=(left.evidence_id,),
    )
    graph.add_claim(
        claim_id="claim-2",
        topic="vehicle_seen",
        statement="Автомобиль свидетелем вечером замечен не был.",
        position="no",
        provider="qwen",
        evidence_ids=(right.evidence_id,),
    )

    result = CrossDocumentContradictionGraph().build(graph)

    assert len(result) == 1
    conflict = result[0]
    assert conflict.cross_document is True
    assert conflict.cross_actor is False
    assert conflict.left_sources[0].page == 2
    assert conflict.right_sources[0].page == 7
    assert conflict.left_sources[0].event_id == "interview-1"
    assert conflict.right_sources[0].event_id == "interview-2"


def test_marks_conflict_between_different_actors() -> None:
    graph = CaseEvidenceGraph()
    witness = EvidenceSource(
        evidence_id="doc:w:page:4:chunk:1",
        document_name="witness.pdf",
        document_fingerprint="w",
        excerpt="Деньги переданы не были.",
        page=4,
        actor="Свидетель",
    )
    investigator = EvidenceSource(
        evidence_id="doc:i:page:9:chunk:3",
        document_name="decision.pdf",
        document_fingerprint="i",
        excerpt="Следствием установлена передача денежных средств.",
        page=9,
        actor="Следователь",
    )
    graph.add_source(witness)
    graph.add_source(investigator)
    graph.add_claim(
        claim_id="witness-claim",
        topic="money_transfer",
        statement="Передачи денег не было.",
        position="no",
        provider="kimi",
        evidence_ids=(witness.evidence_id,),
    )
    graph.add_claim(
        claim_id="investigator-claim",
        topic="money_transfer",
        statement="Передача денег состоялась.",
        position="yes",
        provider="deepseek",
        evidence_ids=(investigator.evidence_id,),
    )

    result = CrossDocumentContradictionGraph().build(graph)

    assert len(result) == 1
    assert result[0].cross_document is True
    assert result[0].cross_actor is True


def test_unsupported_claim_is_not_promoted_to_cross_document_conflict() -> None:
    graph = CaseEvidenceGraph()
    source = EvidenceSource(
        evidence_id="doc:a:page:1:chunk:1",
        document_name="source.pdf",
        document_fingerprint="a",
        excerpt="Событие произошло.",
        page=1,
    )
    graph.add_source(source)
    graph.add_claim(
        claim_id="supported",
        topic="event",
        statement="Событие произошло.",
        position="occurred",
        provider="openai",
        evidence_ids=(source.evidence_id,),
    )
    graph.add_claim(
        claim_id="unsupported",
        topic="event",
        statement="Событие не произошло.",
        position="did_not_occur",
        provider="qwen",
        evidence_ids=("invented:id",),
    )

    assert CrossDocumentContradictionGraph().build(graph) == ()


def test_snapshot_contains_exact_source_references() -> None:
    graph = CaseEvidenceGraph()
    left = EvidenceSource(
        evidence_id="doc:a:page:3:chunk:2",
        document_name="first.pdf",
        document_fingerprint="a",
        excerpt="Подпись принадлежит обвиняемому.",
        page=3,
        actor="Эксперт 1",
        metadata={"chunk_index": 2},
    )
    right = EvidenceSource(
        evidence_id="doc:b:page:11:chunk:1",
        document_name="second.pdf",
        document_fingerprint="b",
        excerpt="Подпись выполнена другим лицом.",
        page=11,
        actor="Эксперт 2",
        metadata={"chunk_index": 1},
    )
    graph.add_source(left)
    graph.add_source(right)
    graph.add_claim(
        claim_id="c1",
        topic="signature_authorship",
        statement="Подпись принадлежит обвиняемому.",
        position="yes",
        provider="openai",
        evidence_ids=(left.evidence_id,),
    )
    graph.add_claim(
        claim_id="c2",
        topic="signature_authorship",
        statement="Подпись обвиняемому не принадлежит.",
        position="no",
        provider="qwen",
        evidence_ids=(right.evidence_id,),
    )

    snapshot = CrossDocumentContradictionGraph().snapshot(graph)

    item = snapshot["contradictions"][0]
    assert item["left_sources"][0]["document_name"] == "first.pdf"
    assert item["left_sources"][0]["page"] == 3
    assert item["left_sources"][0]["chunk_index"] == 2
    assert item["right_sources"][0]["document_name"] == "second.pdf"
    assert snapshot["requires_human_review"] is True
