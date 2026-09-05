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


def embedding():
    return [0.0] * 1536


def test_calls_matter_scoped_rpc_and_preserves_citations():
    client = FakeClient([
        {
            "chunk_id": "chunk-1",
            "document_id": "doc-7",
            "matter_id": "matter-1",
            "source_page": 12,
            "chunk_index": 4,
            "content": "Показания о времени прибытия.",
            "similarity": 0.91,
        }
    ])
    rag = SupabaseMatterRAG(client=client, owner_user_id="owner-1")

    result = rag.retrieve(
        matter_id="matter-1",
        query="время прибытия",
        query_embedding=embedding(),
        limit=5,
    )

    assert client.last_function == "match_matter_document_chunks"
    assert client.last_params["p_matter_id"] == "matter-1"
    assert client.last_params["p_owner_user_id"] == "owner-1"
    assert result.citations == ("document:doc-7:page:12:chunk:4",)
    assert result.results[0].score == pytest.approx(0.91)


def test_rejects_wrong_embedding_dimension():
    rag = SupabaseMatterRAG(client=FakeClient([]), owner_user_id="owner-1")
    with pytest.raises(ValueError, match="1536"):
        rag.retrieve(matter_id="matter-1", query="test", query_embedding=[0.0])


def test_rejects_cross_matter_rpc_response():
    client = FakeClient([
        {
            "chunk_id": "chunk-1",
            "document_id": "doc-2",
            "matter_id": "other-matter",
            "source_page": 1,
            "chunk_index": 0,
            "content": "wrong matter",
            "similarity": 0.9,
        }
    ])
    rag = SupabaseMatterRAG(client=client, owner_user_id="owner-1")

    with pytest.raises(RuntimeError, match="matter isolation"):
        rag.retrieve(
            matter_id="matter-1",
            query="test",
            query_embedding=embedding(),
        )


def test_zero_limit_does_not_call_rpc():
    client = FakeClient([])
    rag = SupabaseMatterRAG(client=client, owner_user_id="owner-1")
    result = rag.retrieve(
        matter_id="matter-1",
        query="test",
        query_embedding=embedding(),
        limit=0,
    )
    assert result.results == ()
    assert client.last_function is None
