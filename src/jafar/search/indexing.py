from dataclasses import dataclass

from jafar.documents.chunking import DocumentChunk, chunk_document
from jafar.documents.ingestion import DocumentContent
from jafar.search.embeddings import EmbeddingProvider


@dataclass(frozen=True)
class IndexedChunkPayload:
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    source: str
    embedding: list[float]
    embedding_model: str


def build_index_payloads(
    document: DocumentContent,
    provider: EmbeddingProvider,
    max_chars: int = 4000,
) -> list[IndexedChunkPayload]:
    chunks: list[DocumentChunk] = chunk_document(document, max_chars=max_chars)
    payloads: list[IndexedChunkPayload] = []
    for index, chunk in enumerate(chunks):
        embedding = provider.embed(chunk.text)
        payloads.append(
            IndexedChunkPayload(
                chunk_id=chunk.chunk_id,
                document_id=document.document_id,
                chunk_index=index,
                content=chunk.text,
                source=chunk.source,
                embedding=embedding.vector,
                embedding_model=embedding.model,
            )
        )
    return payloads
