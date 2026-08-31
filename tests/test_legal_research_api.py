from fastapi.testclient import TestClient

from jafar.contradiction_detector import Contradiction
from jafar.cross_document_analysis import CrossDocumentReport
from jafar.legal_research_service import LegalResearchResult
from jafar.main import app
from jafar.matter_rag import MatterChunk, MatterRAGContext, RetrievedChunk


class StubResearchService:
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail = fail
        self.calls = []

    def research(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail is not None:
            raise self.fail
        matter_id = kwargs["matter_id"]
        question = kwargs["question"]
        chunk = MatterChunk(
            chunk_id="chunk-1",
            matter_id=matter_id,
            document_id="doc-7",
            source_page=12,
            chunk_index=3,
            content="Свидетель указал конкретное время события.",
        )
        context = MatterRAGContext(
            matter_id=matter_id,
            query=question,
            results=(RetrievedChunk(chunk=chunk, score=0.92),),
        )
        return LegalResearchResult(
            matter_id=matter_id,
            question=question,
            answer=f"Ответ [{chunk.citation}]",
            citations=(chunk.citation,),
            contradiction_report=CrossDocumentReport(
                matter_id=matter_id,
                contradictions=(
                    Contradiction(
                        topic="time",
                        left="12:41",
                        right="17:09",
                        evidence_ids=(chunk.citation,),
                        severity="high",
                    ),
                ),
                documents_considered=(chunk.document_id,),
            ),
            context=context,
        )


def test_research_endpoint_returns_citations_and_chunk_count():
    service = StubResearchService()
    app.state.legal_research_service_factory = lambda matter_id: service
    client = TestClient(app)

    response = client.post(
        "/v1/matters/matter-1/research",
        json={"question": "Есть ли противоречия во времени?", "limit": 6},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["matter_id"] == "matter-1"
    assert body["retrieved_chunks"] == 1
    assert body["citations"] == ["document:doc-7:page:12:chunk:3"]
    assert body["contradictions"][0]["severity"] == "high"
    assert service.calls[0]["matter_id"] == "matter-1"
    assert service.calls[0]["limit"] == 6


def test_research_endpoint_is_unavailable_without_runtime_configuration():
    app.state.legal_research_service_factory = None
    client = TestClient(app)

    response = client.post(
        "/v1/matters/matter-1/research",
        json={"question": "Что установлено материалами?"},
    )

    assert response.status_code == 503


def test_research_endpoint_maps_runtime_failure_to_bad_gateway():
    service = StubResearchService(fail=RuntimeError("provider failed"))
    app.state.legal_research_service_factory = lambda matter_id: service
    client = TestClient(app)

    response = client.post(
        "/v1/matters/matter-1/research",
        json={"question": "Что установлено материалами?"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Legal research failed"


def test_research_endpoint_validates_limits():
    service = StubResearchService()
    app.state.legal_research_service_factory = lambda matter_id: service
    client = TestClient(app)

    response = client.post(
        "/v1/matters/matter-1/research",
        json={"question": "Вопрос", "limit": 100},
    )

    assert response.status_code == 422
