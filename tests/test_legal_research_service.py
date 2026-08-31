from types import SimpleNamespace

from jafar.cross_document_analysis import CrossDocumentContradictionService, DocumentClaim
from jafar.legal_research_service import LegalResearchService
from jafar.matter_rag import MatterChunk, MatterRAGContext, RetrievedChunk


class FakeEmbeddings:
    def embed(self, text):
        return (1.0,) * 1536


class FakeRetrieval:
    def retrieve(self, *, matter_id, query, query_embedding, limit=8, min_similarity=0.0):
        chunk = MatterChunk(
            chunk_id="c1",
            matter_id=matter_id,
            document_id="doc-1",
            source_page=2,
            chunk_index=3,
            content="Срок продлен до 10 сентября.",
        )
        return MatterRAGContext(
            matter_id=matter_id,
            query=query,
            results=(RetrievedChunk(chunk=chunk, score=0.9),),
        )


class FakeAnswers:
    def answer(self, *, question, context):
        return f"Ответ [{context.citations[0]}]"


def test_research_returns_matter_scoped_answer_and_citations():
    service = LegalResearchService(
        embeddings=FakeEmbeddings(),
        retrieval=FakeRetrieval(),
        answers=FakeAnswers(),
    )
    result = service.research(matter_id="matter-1", question="Какой срок?")
    assert result.citations == ("document:doc-1:page:2:chunk:3",)
    assert result.answer.endswith("[document:doc-1:page:2:chunk:3]")


def test_research_attaches_cross_document_contradictions():
    claims = [
        DocumentClaim("matter-1", "doc-a", 1, 0, "date", "Событие было 1 мая", "yes"),
        DocumentClaim("matter-1", "doc-b", 4, 2, "date", "Событие было 2 мая", "no"),
    ]
    service = LegalResearchService(
        embeddings=FakeEmbeddings(),
        retrieval=FakeRetrieval(),
        answers=FakeAnswers(),
        contradictions=CrossDocumentContradictionService(),
    )
    result = service.research(matter_id="matter-1", question="Когда событие?", claims=claims)
    assert result.contradiction_report is not None
    contradiction = result.contradiction_report.contradictions[0]
    assert "document:doc-a:page:1:chunk:0" in contradiction.evidence_ids
    assert "document:doc-b:page:4:chunk:2" in contradiction.evidence_ids


def test_research_validates_inputs():
    service = LegalResearchService(FakeEmbeddings(), FakeRetrieval(), FakeAnswers())
    try:
        service.research(matter_id="", question="x")
    except ValueError as exc:
        assert "matter_id" in str(exc)
    else:
        raise AssertionError("expected ValueError")
