from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol, Sequence

from .contradiction_detector import ContradictionGapDetector
from .cross_document_analysis import (
    CrossDocumentContradictionService,
    CrossDocumentReport,
    DocumentClaim,
)
from .matter_rag import MatterRAGContext


_CITATION_TOKEN = re.compile(r"document:[A-Za-z0-9._-]+:page:\d+:chunk:\d+")


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
    contradiction_report: CrossDocumentReport | None
    context: MatterRAGContext

    @property
    def contradictions(self) -> tuple[dict, ...]:
        if self.contradiction_report is None:
            return ()
        rows = ContradictionGapDetector.serialize(list(self.contradiction_report.contradictions))
        return tuple(rows)


@dataclass(slots=True)
class LegalResearchService:
    embeddings: EmbeddingProvider
    retrieval: MatterRAGProvider
    answers: ResearchAnswerProvider
    contradictions: CrossDocumentContradictionService | None = None

    def research(
        self,
        *,
        matter_id: str,
        question: str,
        limit: int = 8,
        min_similarity: float = 0.0,
        claims: Sequence[DocumentClaim] | None = None,
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
        self._validate_answer_citations(answer=answer, context=context)

        contradiction_report = None
        if self.contradictions is not None and claims:
            contradiction_report = self.contradictions.compare(
                matter_id=matter_id,
                claims=claims,
            )

        return LegalResearchResult(
            matter_id=matter_id,
            question=question,
            answer=answer,
            citations=context.citations,
            contradiction_report=contradiction_report,
            context=context,
        )

    @staticmethod
    def _validate_answer_citations(*, answer: str, context: MatterRAGContext) -> None:
        if not context.results:
            return

        cited = tuple(dict.fromkeys(_CITATION_TOKEN.findall(answer)))
        if not cited:
            raise RuntimeError("research answer omitted required Matter citations")

        allowed = set(context.citations)
        unknown = tuple(ref for ref in cited if ref not in allowed)
        if unknown:
            raise RuntimeError(
                "research answer cited sources outside retrieved Matter context: "
                + ", ".join(unknown)
            )
