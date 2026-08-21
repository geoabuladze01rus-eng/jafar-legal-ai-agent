from dataclasses import dataclass

from jafar.documents.ingestion import DocumentContent


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    text: str
    source: str
    page: int | None = None


def chunk_document(document: DocumentContent, max_chars: int = 4000) -> list[DocumentChunk]:
    """Split extracted text while preserving source provenance."""
    if max_chars < 200:
        raise ValueError("max_chars must be at least 200")

    text = document.text.strip()
    if not text:
        return []

    chunks: list[DocumentChunk] = []
    for index, start in enumerate(range(0, len(text), max_chars), start=1):
        part = text[start : start + max_chars].strip()
        if not part:
            continue
        chunks.append(
            DocumentChunk(
                chunk_id=f"{document.document_id}:chunk-{index}",
                text=part,
                source=document.source,
            )
        )
    return chunks
