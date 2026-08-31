from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from .cross_document_analysis import CrossDocumentAnalyzer, SourcedClaim
from .matter_rag import MatterRAGContext


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> Sequence[float]: ...


class MatterRAGProvider(Protocol):
    def retrieve(
        self,
        *,
        matter_id: str,
        query: str,
        query_embedding: Sequence[float],
        limit: int = 8,
        min_similarity: float = 0.0,
    ) -> MatterRAGContext: ...


class ResearchAnswerProvider(Protocol):
    def answer(self, *, question: str, context: MatterRAGContext) -> str: ...


@dataclass(frozen=True, slots=True)
class LegalResearchResult:
    matter_id: str
    question: str
    answer: str
    citations: tuple[str, ...]
    contradictions: tuple[dict, ...]
    context: MatterRAGContext


@dataclass(slots=True)
class LegalResearchService:
    embeddings: EmbeddingProvider
    retrieval: MatterRAGProvider
    answers: ResearchAnswerProvider
    contradiction_analyzer: CrossDocumentAnalyzer | None = None

    def research(
        self,
        *,
        matter_id: str,
        question: str,
        limit: int = 8,
        min_similarity: float = 0.0,
        claims: list[SourcedClaim] | None = None,
    ) -> LegalResearchResult:
        if not matter_id.strip():
            raise ValueError("matter_id is required")
        if not question.strip():
            raise ValueError("question is required")

        query_embedding = self.embeddings.embed(question)
        context = self.retrieval.retrieve(
            matter_id=matter_id,
            query=question,
            query_embedding=query_embedding,
            limit=limit,
            min_similarity=min_similarity,
        )
        answer = self.answers.answer(question=question, context=context)

        contradiction_rows: tuple[dict, ...] = ()
        if self.contradiction_analyzer is not None and claims:
            contradiction_rows = tuple(
                self.contradiction_analyzer.analyze(claims)
            )

        return LegalResearchResult(
            matter_id=matter_id,
            question=question,
            answer=answer,
            citations=context.citations,
            contradictions=contradiction_rows,
            context=context,
        )
