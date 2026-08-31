from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Protocol, Sequence

from .matter_rag import MatterChunk, MatterRAGContext, MatterRetriever, RetrievedChunk


class SupabaseRPCClient(Protocol):
    def rpc(self, function: str, params: dict[str, Any]) -> Any: ...


@dataclass(slots=True)
class SupabaseMatterRAG:
    """Service-role adapter for owner- and matter-scoped pgvector retrieval."""

    client: SupabaseRPCClient
    owner_user_id: str

    EMBEDDING_DIMENSION = 1536
    MAX_RPC_CANDIDATES = 200

    def retrieve(
        self,
        *,
        matter_id: str,
        query: str,
        query_embedding: Sequence[float],
        limit: int = 8,
        min_similarity: float = 0.01,
        per_document_limit: int | None = None,
    ) -> MatterRAGContext:
        if not matter_id.strip():
            raise ValueError("matter_id is required")
        if not self.owner_user_id.strip():
            raise ValueError("owner_user_id is required")
        if not self._valid_embedding(query_embedding):
            raise ValueError("query_embedding must contain 1536 finite values")
        if not isfinite(min_similarity) or not 0.0 <= min_similarity <= 1.0:
            raise ValueError("min_similarity must be between 0 and 1")
        if per_document_limit is not None and per_document_limit <= 0:
            raise ValueError("per_document_limit must be positive")
        bounded_limit = min(max(limit, 0), MatterRetriever.MAX_LIMIT)
        if bounded_limit == 0:
            return MatterRAGContext(
                owner_user_id=self.owner_user_id,
                matter_id=matter_id,
                query=query,
                results=(),
            )

        params = {
            "p_matter_id": matter_id,
            "p_owner_user_id": self.owner_user_id,
            "p_query_embedding": list(query_embedding),
            "p_match_count": min(bounded_limit * 4, self.MAX_RPC_CANDIDATES),
            "p_min_similarity": float(min_similarity),
        }
        response = self.client.rpc("match_matter_document_chunks", params).execute()
        rows = response.data or []
        if not isinstance(rows, list):
            raise RuntimeError("invalid matter retrieval response")

        candidates = [
            retrieved
            for row in rows
            if (retrieved := self._row_to_result(row, matter_id=matter_id)) is not None
            and retrieved.score >= min_similarity
        ]
        results = MatterRetriever.normalize_pre_scored(
            candidates,
            limit=bounded_limit,
            per_document_limit=per_document_limit,
        )
        return MatterRAGContext(
            owner_user_id=self.owner_user_id,
            matter_id=matter_id,
            query=query,
            results=results,
        )

    def _row_to_result(
        self,
        row: Any,
        *,
        matter_id: str,
    ) -> RetrievedChunk | None:
        if not isinstance(row, dict):
            raise RuntimeError("invalid matter retrieval row")
        row_matter_id = str(row.get("matter_id", ""))
        row_owner_id = str(row.get("owner_user_id", ""))
        if row_matter_id != matter_id:
            raise RuntimeError("matter isolation violation in retrieval response")
        if row_owner_id != self.owner_user_id:
            raise RuntimeError("owner isolation violation in retrieval response")

        try:
            source_page = int(row["source_page"])
            chunk_index = int(row["chunk_index"])
            score = float(row["similarity"])
            source_start = self._optional_int(row.get("source_start"))
            source_end = self._optional_int(row.get("source_end"))
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("invalid matter retrieval provenance") from exc
        if source_page < 1 or chunk_index < 0 or not isfinite(score) or not -1.0 <= score <= 1.0:
            raise RuntimeError("invalid matter retrieval provenance")
        if (source_start is None) != (source_end is None):
            raise RuntimeError("incomplete matter retrieval source offsets")
        if source_start is not None and (source_start < 0 or source_end <= source_start):
            raise RuntimeError("invalid matter retrieval source offsets")

        content = str(row.get("content", ""))
        if not content.strip():
            return None
        stable_chunk_id = self._optional_text(row.get("stable_chunk_id"))
        chunk = MatterChunk(
            chunk_id=str(row.get("chunk_id", "")),
            stable_chunk_id=stable_chunk_id,
            owner_user_id=row_owner_id,
            matter_id=row_matter_id,
            document_id=str(row.get("document_id", "")),
            source_page=source_page,
            source_section=self._optional_text(row.get("source_section")),
            source_start=source_start,
            source_end=source_end,
            chunk_index=chunk_index,
            content=content,
            embedding=None,
        )
        if not chunk.chunk_id or not chunk.document_id:
            raise RuntimeError("invalid matter retrieval provenance")
        return RetrievedChunk(chunk=chunk, score=score)

    @classmethod
    def _valid_embedding(cls, embedding: Sequence[float]) -> bool:
        try:
            return len(embedding) == cls.EMBEDDING_DIMENSION and all(
                isfinite(float(value)) for value in embedding
            )
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        return None if value is None else int(value)

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
