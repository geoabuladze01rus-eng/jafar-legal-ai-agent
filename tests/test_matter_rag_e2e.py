from types import SimpleNamespace

import pytest

from jafar.legal_research_service import LegalResearchService
from jafar.supabase_matter_rag import SupabaseMatterRAG


class FakeEmbeddings:
    def embed(self, text):
        assert text
        return (1.0,) * 1536


class FakeRPCRequest:
    def __init__(self, rows):
        self._rows = rows

    def execute(self):
        return SimpleNamespace(data=self._rows)


class FakeSupabaseClient:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def rpc(self, function, params):
        self.calls.append((function, params))
        return FakeRPCRequest(self.rows)


class ContextBoundAnswers:
    def answer(self, *, question, context):
        assert question == "Какой срок продления?"
        assert context.matter_id == "matter-1"
        return f"Срок продлен до 10 сентября [{context.citations[0]}]"


class HallucinatedAnswers:
    def answer(self, *, question, context):
        return "Срок продлен до 11 сентября [document:other:page:9:chunk:9]"


def _row(*, matter_id="matter-1"):
    return {
        "chunk_id": "chunk-1",
        "matter_id": matter_id,
        "document_id": "doc-order",
        "source_page": 4,
        "chunk_index": 2,
        "content": "Срок продлен до 10 сентября.",
        "similarity": 0.94,
    }


def test_matter_rag_e2e_retrieves_rpc_context_and_returns_verified_citation():
    client = FakeSupabaseClient([_row()])
    service = LegalResearchService(
        embeddings=FakeEmbeddings(),
        retrieval=SupabaseMatterRAG(client=client, owner_user_id="owner-1"),
        answers=ContextBoundAnswers(),
    )

    result = service.research(
        matter_id="matter-1",
        question="Какой срок продления?",
        limit=5,
        min_similarity=0.5,
    )

    assert result.answer == (
        "Срок продлен до 10 сентября "
        "[document:doc-order:page:4:chunk:2]"
    )
    assert result.citations == ("document:doc-order:page:4:chunk:2",)
    assert result.context.results[0].chunk.content == "Срок продлен до 10 сентября."

    function, params = client.calls[0]
    assert function == "match_matter_document_chunks"
    assert params["p_matter_id"] == "matter-1"
    assert params["p_owner_user_id"] == "owner-1"
    assert params["p_match_count"] == 5
    assert params["p_min_similarity"] == 0.5
    assert len(params["p_query_embedding"]) == 1536


def test_matter_rag_e2e_fails_closed_on_cross_matter_rpc_row():
    client = FakeSupabaseClient([_row(matter_id="matter-2")])
    service = LegalResearchService(
        embeddings=FakeEmbeddings(),
        retrieval=SupabaseMatterRAG(client=client, owner_user_id="owner-1"),
        answers=ContextBoundAnswers(),
    )

    with pytest.raises(RuntimeError, match="matter isolation violation"):
        service.research(matter_id="matter-1", question="Какой срок продления?")


def test_matter_rag_e2e_rejects_answer_citation_not_returned_by_rpc():
    client = FakeSupabaseClient([_row()])
    service = LegalResearchService(
        embeddings=FakeEmbeddings(),
        retrieval=SupabaseMatterRAG(client=client, owner_user_id="owner-1"),
        answers=HallucinatedAnswers(),
    )

    with pytest.raises(RuntimeError, match="outside retrieved Matter context"):
        service.research(matter_id="matter-1", question="Какой срок продления?")
