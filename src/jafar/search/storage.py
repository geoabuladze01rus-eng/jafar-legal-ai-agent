from dataclasses import asdict
from typing import Protocol

from jafar.search.indexing import IndexedChunkPayload


class ChunkRepository(Protocol):
    def upsert_chunks(self, chunks: list[IndexedChunkPayload]) -> None: ...


class SupabaseChunkRepository:
    """Persistence boundary for pgvector chunks; transport is injected by the app."""

    def __init__(self, client: object) -> None:
        self.client = client

    def upsert_chunks(self, chunks: list[IndexedChunkPayload]) -> None:
        rows = [
            {
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "embedding": chunk.embedding,
                "embedding_model": chunk.embedding_model,
            }
            for chunk in chunks
        ]
        if rows:
            self.client.table("document_chunks").upsert(rows).execute()
