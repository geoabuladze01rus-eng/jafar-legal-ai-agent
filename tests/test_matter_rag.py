import math

import pytest

from jafar.matter_rag import MatterChunk, MatterRetriever


def chunk(
    chunk_id,
    matter_id,
    document_id,
    page,
    index,
    content,
    embedding=None,
    *,
    owner="owner-a",
    stable_id=None,
    section=None,
    source_start=None,
    source_end=None,
):
    return MatterChunk(
        chunk_id=chunk_id,
        owner_user_id=owner,
        matter_id=matter_id,
        document_id=document_id,
        source_page=page,
        chunk_index=index,
        stable_chunk_id=stable_id,
        source_section=section,
        source_start=source_start,
        source_end=source_end,
        content=content,
        embedding=embedding,
    )


def retrieve(chunks, **kwargs):
    return MatterRetriever().retrieve(
        owner_user_id=kwargs.pop("owner_user_id", "owner-a"),
        matter_id=kwargs.pop("matter_id", "matter-a"),
        query=kwargs.pop("query", "срок ходатайства"),
        chunks=chunks,
        **kwargs,
    )


def test_retrieval_never_crosses_owner_or_matter_boundaries():
    chunks = [
        chunk("1", "matter-a", "doc-1", 1, 0, "Срок ходатайства нарушен"),
        chunk("2", "matter-b", "doc-2", 2, 0, "Срок ходатайства нарушен"),
        chunk("3", "matter-a", "doc-3", 3, 0, "Срок ходатайства нарушен", owner="owner-b"),
        chunk("4", "matter-a", "doc-4", 4, 0, "Срок ходатайства нарушен", owner=None),
    ]

    result = retrieve(chunks)

    assert [item.chunk.document_id for item in result.results] == ["doc-1"]
    assert result.owner_user_id == "owner-a"


def test_stable_citation_survives_reindexing_and_retains_provenance():
    original = chunk(
        "db-row-1",
        "matter-a",
        "doc-7",
        12,
        3,
        "Показания свидетеля противоречат протоколу",
        stable_id="v1:content-hash",
        section="Допрос свидетеля",
        source_start=44,
        source_end=91,
    )
    reindexed = chunk(
        "db-row-99",
        "matter-a",
        "doc-7",
        12,
        38,
        original.content,
        stable_id="v1:content-hash",
        section=original.source_section,
        source_start=44,
        source_end=91,
    )

    first = retrieve([original], query="показания свидетеля")
    second = retrieve([reindexed], query="показания свидетеля")

    assert first.citations == second.citations
    assert first.citations == ("document:doc-7:stable:v1:content-hash:page:12",)
    assert first.results[0].chunk.source_section == "Допрос свидетеля"
    assert (first.results[0].chunk.source_start, first.results[0].chunk.source_end) == (44, 91)


def test_legacy_chunk_without_stable_id_uses_legacy_citation():
    result = retrieve(
        [chunk("legacy-row", "matter-a", "doc-7", 12, 3, "Показания свидетеля")],
        query="показания свидетеля",
    )

    assert result.citations == ("document:doc-7:page:12:chunk:3",)


def test_embedding_ranking_and_equal_score_order_are_deterministic():
    chunks = [
        chunk("z", "matter-a", "doc-z", 1, 0, "alpha z", (1.0, 0.0), stable_id="z"),
        chunk("a", "matter-a", "doc-a", 1, 0, "alpha a", (1.0, 0.0), stable_id="a"),
        chunk("b", "matter-a", "doc-b", 1, 0, "beta", (0.0, 1.0), stable_id="b"),
    ]

    first = retrieve(chunks, query="irrelevant", query_embedding=(1.0, 0.0), limit=3)
    second = retrieve(reversed(chunks), query="irrelevant", query_embedding=(1.0, 0.0), limit=3)

    assert [item.chunk.document_id for item in first.results] == ["doc-a", "doc-z"]
    assert first.citations == second.citations


def test_deduplicates_repeated_embeddings_and_document_copies():
    repeated = "Одинаковое показание о сроке ходатайства"
    chunks = [
        chunk("1", "matter-a", "doc-1", 1, 0, repeated, stable_id="same"),
        chunk("2", "matter-a", "doc-1", 1, 4, repeated, stable_id="same"),
        chunk("3", "matter-a", "doc-copy", 1, 0, repeated, stable_id="copy"),
    ]

    assert len(retrieve(chunks).results) == 1


def test_diversifies_documents_without_promoting_irrelevant_content():
    chunks = [
        chunk(str(index), "matter-a", "doc-a", 1, index, f"Срок ходатайства нарушен {index}")
        for index in range(5)
    ]
    chunks.extend(
        [
            chunk("b", "matter-a", "doc-b", 1, 0, "Срок ходатайства соблюден"),
            chunk("c", "matter-a", "doc-c", 1, 0, "Совершенно посторонний текст"),
        ]
    )

    result = retrieve(chunks, limit=4)

    documents = [item.chunk.document_id for item in result.results]
    assert "doc-b" in documents
    assert "doc-c" not in documents
    assert documents.count("doc-a") <= 2


def test_threshold_excludes_zero_and_negative_similarity():
    chunks = [
        chunk("zero", "matter-a", "doc-0", 1, 0, "zero", (0.0, 1.0)),
        chunk("negative", "matter-a", "doc-n", 1, 0, "negative", (-1.0, 0.0)),
        chunk("positive", "matter-a", "doc-p", 1, 0, "positive", (1.0, 0.0)),
    ]

    result = retrieve(chunks, query="none", query_embedding=(1.0, 0.0))

    assert [item.chunk.chunk_id for item in result.results] == ["positive"]


def test_malformed_chunk_vector_falls_back_to_lexical_ranking():
    chunks = [
        chunk("bad-size", "matter-a", "doc-1", 1, 0, "Срок ходатайства первый", (1.0,)),
        chunk("nan", "matter-a", "doc-2", 1, 0, "Срок ходатайства второй", (math.nan, 0.0)),
    ]

    result = retrieve(chunks, query_embedding=(1.0, 0.0))

    assert len(result.results) == 2
    assert all(item.score == 1.0 for item in result.results)


def test_empty_and_large_matter_behaviour_is_bounded():
    assert retrieve([], limit=8).results == ()
    chunks = [
        chunk(str(index), "matter-a", "doc-only", index // 100 + 1, index, f"Срок {index}")
        for index in range(1_000)
    ]

    result = retrieve(chunks, query="срок", limit=500)

    assert len(result.results) == MatterRetriever.MAX_LIMIT


@pytest.mark.parametrize("owner,matter", [("", "matter-a"), ("owner-a", "")])
def test_requires_explicit_scope(owner, matter):
    with pytest.raises(ValueError):
        MatterRetriever().retrieve(
            owner_user_id=owner,
            matter_id=matter,
            query="test",
            chunks=[],
        )


def test_rejects_malformed_query_vector_and_invalid_document_cap():
    with pytest.raises(ValueError, match="query_embedding"):
        retrieve([], query_embedding=(math.nan,))
    with pytest.raises(ValueError, match="per_document_limit"):
        retrieve([], per_document_limit=0)
    with pytest.raises(ValueError, match="min_relevance"):
        retrieve([], min_relevance=-0.1)
