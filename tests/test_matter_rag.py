from jafar.matter_rag import MatterChunk, MatterRetriever


def chunk(chunk_id, matter_id, document_id, page, index, content, embedding=None):
    return MatterChunk(
        chunk_id=chunk_id,
        matter_id=matter_id,
        document_id=document_id,
        source_page=page,
        chunk_index=index,
        content=content,
        embedding=embedding,
    )


def test_retrieval_never_crosses_matter_boundary():
    chunks = [
        chunk("1", "matter-a", "doc-1", 1, 0, "Срок рассмотрения ходатайства нарушен"),
        chunk("2", "matter-b", "doc-2", 2, 0, "Срок рассмотрения ходатайства нарушен полностью"),
    ]
    result = MatterRetriever().retrieve(
        matter_id="matter-a",
        query="срок ходатайства",
        chunks=chunks,
    )
    assert len(result.results) == 1
    assert result.results[0].chunk.document_id == "doc-1"


def test_retrieval_exposes_stable_page_chunk_citations():
    chunks = [chunk("1", "matter-a", "doc-7", 12, 3, "Показания свидетеля противоречат протоколу")]
    result = MatterRetriever().retrieve(
        matter_id="matter-a",
        query="показания свидетеля",
        chunks=chunks,
    )
    assert result.citations == ("document:doc-7:page:12:chunk:3",)
    assert "[document:doc-7:page:12:chunk:3]" in result.render()


def test_embedding_ranking_is_used_when_available():
    chunks = [
        chunk("1", "matter-a", "doc-1", 1, 0, "alpha", (1.0, 0.0)),
        chunk("2", "matter-a", "doc-2", 1, 0, "beta", (0.0, 1.0)),
    ]
    result = MatterRetriever().retrieve(
        matter_id="matter-a",
        query="irrelevant",
        query_embedding=(0.9, 0.1),
        chunks=chunks,
        limit=1,
    )
    assert result.results[0].chunk.document_id == "doc-1"
