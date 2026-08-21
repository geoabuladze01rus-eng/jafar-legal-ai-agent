from dataclasses import dataclass

from jafar.documents.ingestion import DocumentContent
from jafar.search.embeddings import EmbeddingProvider
from jafar.search.indexing import IndexedChunkPayload, build_index_payloads
from jafar.search.storage import ChunkRepository


@dataclass(frozen=True)
class IndexingResult:
    document_id: str
    chunks_indexed: int
    embedding_model: str


def index_document(
    document: DocumentContent,
    embedding_provider: EmbeddingProvider,
    chunk_repository: ChunkRepository,
    max_chars: int = 4000,
) -> IndexingResult:
    payloads: list[IndexedChunkPayload] = build_index_payloads(
        document, embedding_provider, max_chars=max_chars
    )
    chunk_repository.upsert_chunks(payloads)
    return IndexingResult(
        document_id=document.document_id,
        chunks_indexed=len(payloads),
        embedding_model=embedding_provider.model,
    )
