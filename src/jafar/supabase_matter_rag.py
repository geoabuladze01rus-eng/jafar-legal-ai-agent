from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from .matter_rag import MatterChunk, MatterRAGContext, RetrievedChunk


class SupabaseRPCClient(Protocol):
    def rpc(self, function: str, params: dict[str, Any]) -> Any: ...


@dataclass(slots=True)
class SupabaseMatterRAG:
    """Production adapter for matter-scoped pgvector retrieval in Supabase."""

    client: SupabaseRPCClient
    owner_user_id: str

    def retrieve(
        self,
        *,
        matter_id: str,
        query: str,
        query_embedding: Sequence[float],
        limit: int = 8,
        min_similarity: float = 0.0,
    ) -> MatterRAGContext:
        if not matter_id.strip():
            raise ValueError("matter_id is required")
        if not self.owner_user_id.strip():
            raise ValueError("owner_user_id is required")
        if len(query_embedding) != 1536:
            raise ValueError("query_embedding must contain 1536 values")
        if limit <= 0:
            return MatterRAGContext(matter_id=matter_id, query=query, results=())

        params = {
            "p_matter_id": matter_id,
            "p_owner_user_id": self.owner_user_id,
            "p_query_embedding": list(query_embedding),
            "p_match_count": min(limit, 50),
            "p_min_similarity": float(min_similarity),
        }
        response = self.client.rpc("match_matter_document_chunks", params).execute()
        rows = response.data or []

        results: list[RetrievedChunk] = []
        for row in rows:
            row_matter_id = str(row["matter_id"])
            if row_matter_id != matter_id:
                raise RuntimeError("matter isolation violation in retrieval response")
            chunk = MatterChunk(
                chunk_id=str(row["chunk_id"]),
                matter_id=row_matter_id,
                document_id=str(row["document_id"]),
                source_page=int(row["source_page"]),
                chunk_index=int(row["chunk_index"]),
                content=str(row["content"]),
                embedding=None,
            )
            results.append(
                RetrievedChunk(chunk=chunk, score=float(row.get("similarity", 0.0)))
            )

        return MatterRAGContext(
            matter_id=matter_id,
            query=query,
            results=tuple(results),
        )
