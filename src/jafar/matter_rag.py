from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite, sqrt
from typing import Iterable, Sequence


@dataclass(frozen=True, slots=True)
class MatterChunk:
    """A source-grounded chunk. Document text is always treated as untrusted data."""

    chunk_id: str
    matter_id: str
    document_id: str
    source_page: int
    chunk_index: int
    content: str
    embedding: tuple[float, ...] | None = None
    owner_user_id: str | None = None
    stable_chunk_id: str | None = None
    source_section: str | None = None
    source_start: int | None = None
    source_end: int | None = None

    @property
    def canonical_chunk_id(self) -> str:
        return self.stable_chunk_id or self.chunk_id

    @property
    def citation(self) -> str:
        if self.stable_chunk_id:
            return (
                f"document:{self.document_id}:stable:{self.stable_chunk_id}"
                f":page:{self.source_page}"
            )
        return self.legacy_citation

    @property
    def legacy_citation(self) -> str:
        return f"document:{self.document_id}:page:{self.source_page}:chunk:{self.chunk_index}"

    @property
    def content_fingerprint(self) -> str:
        normalized = " ".join(self.content.casefold().split())
        return sha256(normalized.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk: MatterChunk
    score: float


@dataclass(frozen=True, slots=True)
class MatterRAGContext:
    matter_id: str
    query: str
    results: tuple[RetrievedChunk, ...]
    owner_user_id: str | None = None

    @property
    def citations(self) -> tuple[str, ...]:
        return tuple(item.chunk.citation for item in self.results)

    def render(self) -> str:
        return "\n\n".join(
            f"[{item.chunk.citation}]\n{item.chunk.content}"
            for item in self.results
        )


class MatterRetriever:
    """Owner- and matter-scoped retrieval with deterministic, diverse ranking."""

    MAX_LIMIT = 50

    @classmethod
    def normalize_pre_scored(
        cls,
        results: Iterable[RetrievedChunk],
        *,
        limit: int,
        per_document_limit: int | None = None,
    ) -> tuple[RetrievedChunk, ...]:
        """Apply the canonical deterministic/deduplication policy to RPC-ranked rows."""
        bounded_limit = min(max(limit, 0), cls.MAX_LIMIT)
        if bounded_limit == 0:
            return ()
        ranked = sorted(results, key=cls._ranking_key)
        deduplicated = cls._deduplicate(ranked)
        return tuple(
            cls._diversify(
                deduplicated,
                limit=bounded_limit,
                per_document_limit=per_document_limit,
            )
        )

    def retrieve(
        self,
        *,
        owner_user_id: str,
        matter_id: str,
        query: str,
        chunks: Iterable[MatterChunk],
        query_embedding: Sequence[float] | None = None,
        limit: int = 8,
        min_relevance: float = 0.01,
        per_document_limit: int | None = None,
    ) -> MatterRAGContext:
        if not owner_user_id.strip():
            raise ValueError("owner_user_id is required")
        if not matter_id.strip():
            raise ValueError("matter_id is required")
        if not isfinite(min_relevance) or not 0.0 <= min_relevance <= 1.0:
            raise ValueError("min_relevance must be between 0 and 1")
        if query_embedding is not None and (
            not query_embedding or not all(isfinite(value) for value in query_embedding)
        ):
            raise ValueError("query_embedding must be non-empty and finite")
        if per_document_limit is not None and per_document_limit <= 0:
            raise ValueError("per_document_limit must be positive")
        bounded_limit = min(max(limit, 0), self.MAX_LIMIT)
        if bounded_limit == 0:
            return MatterRAGContext(
                owner_user_id=owner_user_id,
                matter_id=matter_id,
                query=query,
                results=(),
            )

        ranked: list[RetrievedChunk] = []
        for chunk in chunks:
            if (
                chunk.owner_user_id != owner_user_id
                or chunk.matter_id != matter_id
                or not chunk.content.strip()
            ):
                continue
            score = self._score(query, query_embedding, chunk)
            if score >= min_relevance:
                ranked.append(RetrievedChunk(chunk=chunk, score=score))

        selected = self.normalize_pre_scored(
            ranked,
            limit=bounded_limit,
            per_document_limit=per_document_limit,
        )
        return MatterRAGContext(
            owner_user_id=owner_user_id,
            matter_id=matter_id,
            query=query,
            results=selected,
        )

    def _score(
        self,
        query: str,
        query_embedding: Sequence[float] | None,
        chunk: MatterChunk,
    ) -> float:
        if query_embedding is not None and chunk.embedding is not None:
            cosine = self._cosine(query_embedding, chunk.embedding)
            if cosine is not None:
                return cosine
        return self._lexical_score(query, chunk.content)

    @staticmethod
    def _ranking_key(item: RetrievedChunk) -> tuple[float, str, int, str, int]:
        chunk = item.chunk
        return (
            -item.score,
            chunk.document_id,
            chunk.source_page,
            chunk.canonical_chunk_id,
            chunk.chunk_index,
        )

    @staticmethod
    def _deduplicate(ranked: list[RetrievedChunk]) -> list[RetrievedChunk]:
        seen_identity: set[tuple[str, str]] = set()
        seen_content: set[str] = set()
        result: list[RetrievedChunk] = []
        for item in ranked:
            identity = (item.chunk.document_id, item.chunk.canonical_chunk_id)
            fingerprint = item.chunk.content_fingerprint
            if identity in seen_identity or fingerprint in seen_content:
                continue
            seen_identity.add(identity)
            seen_content.add(fingerprint)
            result.append(item)
        return result

    @staticmethod
    def _diversify(
        ranked: list[RetrievedChunk],
        *,
        limit: int,
        per_document_limit: int | None,
    ) -> list[RetrievedChunk]:
        if not ranked:
            return []
        documents = {item.chunk.document_id for item in ranked}
        cap = per_document_limit
        if cap is None:
            cap = limit if len(documents) == 1 else max(2, (limit + 1) // 2)

        selected: list[RetrievedChunk] = []
        selected_ids: set[tuple[str, str]] = set()
        document_counts: dict[str, int] = {}
        diversity_floor = ranked[0].score * 0.5 if ranked[0].score > 0 else ranked[0].score

        for item in ranked:
            document_id = item.chunk.document_id
            if document_id in document_counts or item.score < diversity_floor:
                continue
            selected.append(item)
            selected_ids.add((document_id, item.chunk.canonical_chunk_id))
            document_counts[document_id] = 1
            if len(selected) == limit:
                return sorted(selected, key=MatterRetriever._ranking_key)

        for item in ranked:
            identity = (item.chunk.document_id, item.chunk.canonical_chunk_id)
            if identity in selected_ids:
                continue
            count = document_counts.get(item.chunk.document_id, 0)
            if count >= cap:
                continue
            selected.append(item)
            selected_ids.add(identity)
            document_counts[item.chunk.document_id] = count + 1
            if len(selected) == limit:
                break
        return sorted(selected, key=MatterRetriever._ranking_key)

    @staticmethod
    def _cosine(left: Sequence[float], right: Sequence[float]) -> float | None:
        if len(left) != len(right) or not left or not all(isfinite(value) for value in right):
            return None
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = sqrt(sum(a * a for a in left))
        right_norm = sqrt(sum(b * b for b in right))
        if not left_norm or not right_norm:
            return None
        score = dot / (left_norm * right_norm)
        return score if isfinite(score) else None

    @staticmethod
    def _lexical_score(query: str, content: str) -> float:
        query_terms = {term for term in re.findall(r"[\wёЁ]+", query.casefold()) if len(term) > 2}
        if not query_terms:
            return 0.0
        content_terms = set(re.findall(r"[\wёЁ]+", content.casefold()))
        return len(query_terms & content_terms) / len(query_terms)
