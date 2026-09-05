from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable, Sequence


@dataclass(frozen=True, slots=True)
class MatterChunk:
    chunk_id: str
    matter_id: str
    document_id: str
    source_page: int
    chunk_index: int
    content: str
    embedding: tuple[float, ...] | None = None

    @property
    def citation(self) -> str:
        return f"document:{self.document_id}:page:{self.source_page}:chunk:{self.chunk_index}"


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk: MatterChunk
    score: float


@dataclass(frozen=True, slots=True)
class MatterRAGContext:
    matter_id: str
    query: str
    results: tuple[RetrievedChunk, ...]

    @property
    def citations(self) -> tuple[str, ...]:
        return tuple(item.chunk.citation for item in self.results)

    def render(self) -> str:
        return "\n\n".join(
            f"[{item.chunk.citation}]\n{item.chunk.content}"
            for item in self.results
        )


class MatterRetriever:
    """Matter-scoped retrieval with deterministic citation metadata."""

    def retrieve(
        self,
        *,
        matter_id: str,
        query: str,
        chunks: Iterable[MatterChunk],
        query_embedding: Sequence[float] | None = None,
        limit: int = 8,
    ) -> MatterRAGContext:
        if limit <= 0:
            return MatterRAGContext(matter_id=matter_id, query=query, results=())

        candidates = [
            chunk for chunk in chunks
            if chunk.matter_id == matter_id and chunk.content.strip()
        ]
        ranked: list[RetrievedChunk] = []
        for chunk in candidates:
            if query_embedding is not None and chunk.embedding is not None:
                score = self._cosine(query_embedding, chunk.embedding)
            else:
                score = self._lexical_score(query, chunk.content)
            ranked.append(RetrievedChunk(chunk=chunk, score=score))

        ranked.sort(key=lambda item: (item.score, -item.chunk.chunk_index), reverse=True)
        return MatterRAGContext(
            matter_id=matter_id,
            query=query,
            results=tuple(ranked[:limit]),
        )

    @staticmethod
    def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
        if len(left) != len(right) or not left:
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = sqrt(sum(a * a for a in left))
        right_norm = sqrt(sum(b * b for b in right))
        if not left_norm or not right_norm:
            return 0.0
        return dot / (left_norm * right_norm)

    @staticmethod
    def _lexical_score(query: str, content: str) -> float:
        query_terms = {term for term in query.casefold().split() if len(term) > 2}
        if not query_terms:
            return 0.0
        content_folded = content.casefold()
        hits = sum(1 for term in query_terms if term in content_folded)
        return hits / len(query_terms)
