from jafar.document_intake import ExtractedDocument
from jafar.evidence_graph import CaseEvidenceGraph


def test_pdf_like_pages_produce_page_aware_fragment_ids() -> None:
    document = ExtractedDocument(
        filename="case.pdf",
        media_type="application/pdf",
        text="page one text\npage two text",
        pages=("page one text", "page two text"),
    )

    fragments = document.fragments(max_chars=200)

    assert len(fragments) == 2
    assert fragments[0].page == 1
    assert fragments[1].page == 2
    assert ":page:1:chunk:0" in document.evidence_id(fragments[0])
    assert ":page:2:chunk:1" in document.evidence_id(fragments[1])


def test_fragment_ids_are_stable_for_same_document_content() -> None:
    first = ExtractedDocument(
        filename="first-name.pdf",
        media_type="application/pdf",
        text="same content",
        pages=("same content",),
    )
    second = ExtractedDocument(
        filename="renamed.pdf",
        media_type="application/pdf",
        text="same content",
        pages=("same content",),
    )

    assert first.fingerprint == second.fingerprint
    assert first.evidence_id(first.fragments()[0]) == second.evidence_id(second.fragments()[0])


def test_evidence_graph_registers_fragment_metadata() -> None:
    document = ExtractedDocument(
        filename="protocol.pdf",
        media_type="application/pdf",
        text="statement one\nstatement two",
        pages=("statement one", "statement two"),
    )
    graph = CaseEvidenceGraph()

    sources = graph.add_document_fragments(document, actor="witness-a", event_id="event-1")

    assert len(sources) == 2
    assert sources[0].page == 1
    assert sources[0].actor == "witness-a"
    assert sources[0].event_id == "event-1"
    assert sources[0].metadata["chunk_index"] == 0
    assert graph.source(sources[0].evidence_id) == sources[0]
