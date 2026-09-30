from __future__ import annotations

import pytest

from jafar.desktop_corpus_service import DesktopCorpusService
from jafar.desktop_legal_research import (
    DesktopMatterRAGProvider,
    OllamaDesktopResearchAnswerProvider,
    build_desktop_legal_research_service,
)
from jafar.encrypted_desktop_corpus import EncryptedDesktopCorpusStore


class FakeStructuredProvider:
    def __init__(self, citation: str | None = None) -> None:
        self.citation = citation

    def complete_structured(self, *, system_prompt, user_prompt, response_model):
        assert "локальный юридический ИИ-помощник" in system_prompt
        assert "Материалы выбранного дела" in user_prompt
        citations = [self.citation] if self.citation else []
        return response_model(
            answer="В материалах указано, что договор был заключён.",
            citations=citations,
        )


def _store(tmp_path):
    store = EncryptedDesktopCorpusStore(
        tmp_path / "corpus.sqlite3",
        tmp_path / "documents",
        b"k" * 32,
    )
    service = DesktopCorpusService(store)
    first = service.import_document(
        matter_id="matter-1",
        filename="contract.txt",
        media_type="text/plain",
        original_bytes=b"SYNTHETIC CONTRACT",
        extracted_text="Договор был заключён 01.09.2026. Оплата предусмотрена договором.",
    )
    service.import_document(
        matter_id="matter-2",
        filename="other.txt",
        media_type="text/plain",
        original_bytes=b"OTHER MATTER",
        extracted_text="Совершенно иные обстоятельства другого дела.",
    )
    return store, first


def test_desktop_retrieval_never_crosses_matter_boundary(tmp_path):
    store, first = _store(tmp_path)
    context = DesktopMatterRAGProvider(store).retrieve(
        matter_id="matter-1",
        query="договор оплата",
        query_embedding=(),
        limit=8,
    )

    assert context.results
    assert all(item.chunk.matter_id == "matter-1" for item in context.results)
    assert any(item.chunk.document_id == first.document_id for item in context.results)
    assert all("other.txt" not in item.chunk.content for item in context.results)
    store.close()


def test_local_research_answer_requires_known_matter_citation(tmp_path):
    store, _ = _store(tmp_path)
    context = store.retrieve("matter-1", "договор", limit=8)
    citation = context.citations[0]

    provider = OllamaDesktopResearchAnswerProvider(FakeStructuredProvider(citation))
    answer = provider.answer(question="Что известно о договоре?", context=context)

    assert "договор был заключён" in answer
    assert citation in answer
    store.close()


def test_local_research_rejects_unknown_citation(tmp_path):
    store, _ = _store(tmp_path)
    context = store.retrieve("matter-1", "договор", limit=8)

    provider = OllamaDesktopResearchAnswerProvider(
        FakeStructuredProvider("document:other:page:1:chunk:0")
    )
    with pytest.raises(RuntimeError, match="outside selected Matter"):
        provider.answer(question="Что известно?", context=context)
    store.close()


def test_desktop_research_service_returns_scoped_citations(tmp_path):
    store, _ = _store(tmp_path)
    context = store.retrieve("matter-1", "договор", limit=8)
    citation = context.citations[0]
    service = build_desktop_legal_research_service(
        store,
        FakeStructuredProvider(citation),
    )

    result = service.research(
        matter_id="matter-1",
        question="Что известно о договоре?",
        limit=8,
    )

    assert result.matter_id == "matter-1"
    assert result.citations
    assert all(ref.startswith("document:") for ref in result.citations)
    assert citation in result.answer
    store.close()


def test_desktop_retrieval_returns_no_zero_relevance_context(tmp_path):
    store, _ = _store(tmp_path)
    context = DesktopMatterRAGProvider(store).retrieve(
        matter_id="matter-1",
        query="космический спутник марсианская экспедиция",
        query_embedding=(),
        limit=8,
    )

    assert context.results == ()
    store.close()
