from jafar.evidence_graph import CaseEvidenceGraph, EvidenceSource


def test_claim_is_supported_only_when_all_evidence_sources_exist() -> None:
    graph = CaseEvidenceGraph()
    graph.add_source(
        EvidenceSource(
            evidence_id="doc-1:p14",
            document_name="interrogation.pdf",
            document_fingerprint="abc",
            excerpt="Свидетель указал на 13 августа.",
            page=14,
            actor="Свидетель Иванов",
        )
    )

    supported = graph.add_claim(
        claim_id="claim-1",
        topic="arrival_date",
        statement="Свидетель указывает на 13 августа.",
        position="supports",
        provider="qwen",
        evidence_ids=("doc-1:p14",),
    )
    unsupported = graph.add_claim(
        claim_id="claim-2",
        topic="arrival_date",
        statement="Есть иной документ о 14 августа.",
        position="contradicts",
        provider="kimi",
        evidence_ids=("missing:p22",),
    )

    assert supported.supported is True
    assert unsupported.supported is False
    assert graph.unsupported_claims() == (unsupported,)
    assert graph.snapshot()["requires_human_review"] is True


def test_claim_without_source_reference_never_counts_as_supported() -> None:
    graph = CaseEvidenceGraph()
    claim = graph.add_claim(
        claim_id="claim-1",
        topic="qualification",
        statement="Квалификация может быть спорной.",
        position="uncertain",
        provider="openai",
        evidence_ids=(),
    )

    assert claim.supported is False
    assert graph.snapshot()["requires_human_review"] is True
