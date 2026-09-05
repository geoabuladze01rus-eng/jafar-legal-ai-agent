from jafar.cross_document_analysis import (
    CrossDocumentContradictionService,
    DocumentClaim,
)


def claim(document_id, page, chunk_index, statement, position, matter_id="matter-a"):
    return DocumentClaim(
        matter_id=matter_id,
        document_id=document_id,
        source_page=page,
        chunk_index=chunk_index,
        topic="время события",
        statement=statement,
        position=position,
    )


def test_cross_document_report_preserves_both_source_citations():
    report = CrossDocumentContradictionService().compare(
        matter_id="matter-a",
        claims=[
            claim("doc-1", 4, 1, "Событие произошло в 10:00", "10:00"),
            claim("doc-2", 7, 2, "Событие произошло в 12:00", "12:00"),
        ],
    )
    assert len(report.contradictions) == 1
    evidence = report.contradictions[0].evidence_ids
    assert "document:doc-1:page:4:chunk:1" in evidence
    assert "document:doc-2:page:7:chunk:2" in evidence
    assert report.documents_considered == ("doc-1", "doc-2")


def test_cross_document_comparison_does_not_mix_matters():
    report = CrossDocumentContradictionService().compare(
        matter_id="matter-a",
        claims=[
            claim("doc-1", 4, 1, "Событие произошло в 10:00", "10:00"),
            claim("doc-2", 7, 2, "Событие произошло в 12:00", "12:00", matter_id="matter-b"),
        ],
    )
    assert report.contradictions == ()
    assert report.documents_considered == ("doc-1",)
