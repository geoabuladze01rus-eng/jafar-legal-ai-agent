from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .memory_models import MemoryKind, MemoryRecord, MemorySearchResult
from .supabase_memory_repository import SupabaseMemoryRepository


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> tuple[float, ...]: ...


@dataclass(slots=True)
class LongTermMemoryService:
    repository: SupabaseMemoryRepository
    embeddings: EmbeddingProvider

    def remember(
        self,
        *,
        content: str,
        kind: MemoryKind = MemoryKind.NOTE,
        matter_id: str | None = None,
        source: str | None = None,
        confidence: float = 1.0,
    ) -> MemoryRecord:
        text = content.strip()
        if not text:
            raise ValueError("memory content is required")
        embedding = self.embeddings.embed(text)
        return self.repository.add(
            kind=kind,
            content=text,
            embedding=embedding,
            matter_id=matter_id,
            source=source,
            confidence=confidence,
        )

    def recall(
        self,
        query: str,
        *,
        matter_id: str | None = None,
        limit: int = 8,
        min_similarity: float = 0.0,
    ) -> list[MemorySearchResult]:
        text = query.strip()
        if not text:
            raise ValueError("memory query is required")
        return self.repository.search(
            embedding=self.embeddings.embed(text),
            matter_id=matter_id,
            limit=limit,
            min_similarity=min_similarity,
        )

    def list_memories(self, *, matter_id: str | None = None, limit: int = 100) -> list[MemoryRecord]:
        return self.repository.list(matter_id=matter_id, limit=limit)

    def forget(self, memory_id: str) -> bool:
        if not memory_id.strip():
            raise ValueError("memory id is required")
        return self.repository.delete(memory_id.strip())
