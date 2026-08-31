import math

import pytest

from jafar.supabase_matter_rag import SupabaseMatterRAG


class Response:
    def __init__(self, data):
        self.data = data


class RPC:
    def __init__(self, client, function, params):
        self.client = client
        self.function = function
        self.params = params

    def execute(self):
        self.client.last_function = self.function
        self.client.last_params = self.params
        return Response(self.client.data)


class FakeClient:
    def __init__(self, data):
        self.data = data
        self.last_function = None
        self.last_params = None

    def rpc(self, function, params):
        return RPC(self, function, params)


def embedding(value=0.0):
    return [value] * 1536


def row(
    chunk_id,
    document_id,
    *,
    content="Показания о времени прибытия.",
    stable_id=None,
    owner="owner-1",
    matter="matter-1",
    page=12,
    index=4,
    section="Протокол допроса",
    source_start=40,
    source_end=78,
    similarity=0.91,
):
    return {
        "chunk_id": chunk_id,
        "stable_chunk_id": stable_id,
        "document_id": document_id,
        "matter_id": matter,
        "owner_user_id": owner,
        "source_page": page,
        "source_section": section,
        "source_start": source_start,
        "source_end": source_end,
        "chunk_index": index,
        "content": content,
        "similarity": similarity,
    }


def retrieve(data, **kwargs):
    client = FakeClient(data)
    result = SupabaseMatterRAG(client=client, owner_user_id=kwargs.pop("owner", "owner-1")).retrieve(
        matter_id=kwargs.pop("matter_id", "matter-1"),
        query=kwargs.pop("query", "время прибытия"),
        query_embedding=kwargs.pop("query_embedding", embedding()),
        **kwargs,
    )
    return client, result


def test_calls_scoped_rpc_and_preserves_canonical_provenance():
    client, result = retrieve(
        [row("db-row-1", "doc-7", stable_id="v1:content-hash")],
        limit=5,
        min_similarity=0.25,
    )

    assert client.last_function == "match_matter_document_chunks"
    assert client.last_params == {
        "p_matter_id": "matter-1",
        "p_owner_user_id": "owner-1",
        "p_query_embedding": embedding(),
        "p_match_count": 20,
        "p_min_similarity": 0.25,
    }
    assert result.owner_user_id == "owner-1"
    assert result.citations == ("document:doc-7:stable:v1:content-hash:page:12",)
    chunk = result.results[0].chunk
    assert chunk.source_section == "Протокол допроса"
    assert (chunk.source_start, chunk.source_end) == (40, 78)
    assert result.results[0].score == pytest.approx(0.91)


def test_legacy_row_without_stable_id_keeps_legacy_citation():
    _, result = retrieve([row("legacy-row", "doc-7", stable_id=None)])

    assert result.citations == ("document:doc-7:page:12:chunk:4",)


@pytest.mark.parametrize(
    "bad_embedding",
    [
        [0.0],
        [math.nan] * 1536,
        [math.inf] * 1536,
        ["invalid"] * 1536,
    ],
)
def test_rejects_wrong_or_nonfinite_embedding(bad_embedding):
    with pytest.raises(ValueError, match="1536 finite"):
        retrieve([], query_embedding=bad_embedding)


@pytest.mark.parametrize("minimum", [-0.1, 1.1, math.nan])
def test_rejects_invalid_similarity_threshold(minimum):
    with pytest.raises(ValueError, match="min_similarity"):
        retrieve([], min_similarity=minimum)


def test_rejects_cross_matter_and_cross_owner_rpc_responses():
    with pytest.raises(RuntimeError, match="matter isolation"):
        retrieve([row("1", "doc-1", matter="other-matter")])
    with pytest.raises(RuntimeError, match="owner isolation"):
        retrieve([row("1", "doc-1", owner="other-owner")])
    with pytest.raises(RuntimeError, match="owner isolation"):
        data = row("1", "doc-1")
        data.pop("owner_user_id")
        retrieve([data])


def test_defensively_filters_below_threshold_and_empty_content():
    _, result = retrieve(
        [
            row("good", "doc-1", similarity=0.8),
            row("low", "doc-2", similarity=0.1),
            row("empty", "doc-3", content="  ", similarity=0.9),
        ],
        min_similarity=0.5,
    )

    assert [item.chunk.chunk_id for item in result.results] == ["good"]


def test_rpc_results_are_deduplicated_diversified_and_deterministic():
    data = [
        row("a1", "doc-a", content="Факт один", stable_id="same", similarity=0.99, index=1),
        row("a2", "doc-a", content="Факт один", stable_id="same", similarity=0.98, index=2),
        row("copy", "doc-copy", content="Факт один", stable_id="copy", similarity=0.97),
        row("a3", "doc-a", content="Факт два", stable_id="a3", similarity=0.96),
        row("b1", "doc-b", content="Независимый факт", stable_id="b1", similarity=0.90),
    ]

    _, first = retrieve(data, limit=3)
    _, second = retrieve(list(reversed(data)), limit=3)

    assert first.citations == second.citations
    assert [item.chunk.document_id for item in first.results] == ["doc-a", "doc-a", "doc-b"]
    assert sum(item.chunk.content == "Факт один" for item in first.results) == 1


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"source_page": 0}, "provenance"),
        ({"chunk_index": -1}, "provenance"),
        ({"similarity": math.nan}, "provenance"),
        ({"source_start": None, "source_end": 20}, "source offsets"),
        ({"source_start": 20, "source_end": 10}, "source offsets"),
    ],
)
def test_rejects_malformed_provenance(changes, match):
    data = row("1", "doc-1")
    data.update(changes)

    with pytest.raises(RuntimeError, match=match):
        retrieve([data])


def test_zero_limit_does_not_call_rpc_and_large_limit_is_bounded():
    client, result = retrieve([], limit=0)
    assert result.results == ()
    assert client.last_function is None

    client, _ = retrieve([], limit=5_000)
    assert client.last_params["p_match_count"] == SupabaseMatterRAG.MAX_RPC_CANDIDATES


def test_rejects_invalid_rpc_container_and_document_cap():
    with pytest.raises(RuntimeError, match="invalid matter retrieval response"):
        retrieve({"not": "a list"})
    with pytest.raises(ValueError, match="per_document_limit"):
        retrieve([], per_document_limit=0)
