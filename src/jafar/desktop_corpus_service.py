"""Explicit local document import into the encrypted desktop corpus.

Physical PDF page numbers are retained only when provided by the native PDF
parser. Other formats use source_page=0 (unknown), never an invented page 1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .case_acceptance import VerificationStatus
from .document_parsers import ParsedPage
from .encrypted_desktop_corpus import CorpusDocument, EncryptedDesktopCorpusStore
from .legal_chunking import semantic_legal_chunks
from .matter_rag import MatterChunk


def _canonical(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


class DesktopCorpusService:
    def __init__(self, store: EncryptedDesktopCorpusStore) -> None:
        self.store = store

    def import_document(
        self,
        *,
        matter_id: str,
        filename: str,
        media_type: str,
        original_bytes: bytes,
        extracted_text: str,
        pages: Sequence[ParsedPage] = (),
    ) -> CorpusDocument:
        if pages:
            if Path(filename).suffix.lower() != ".pdf":
                raise ValueError("Physical page provenance is supported only for native PDF")
            if any(page.page_number < 1 for page in pages):
                raise ValueError("Invalid physical PDF page number")
            if list(page.page_number for page in pages) != list(range(1, len(pages) + 1)):
                raise ValueError("Physical PDF pages must be unique and sequential")
            if _canonical("\n".join(page.text for page in pages)) != _canonical(extracted_text):
                raise ValueError("Physical PDF page text does not match extracted content")

        chunks: list[MatterChunk] = []
        provenance: list[dict[str, object]] = []
        facts: list[dict[str, object]] = []

        # If the native parser can prove physical PDF boundaries, never merge
        # chunks across pages. Empty scanned pages remain absent from the RAG
        # index and require separate OCR/visual verification.
        page_sources = list(pages) if pages else [ParsedPage(0, extracted_text)]
        for page in page_sources:
            for legal_chunk in semantic_legal_chunks(
                page.text, source_page=page.page_number
            ):
                chunks.append(
                    MatterChunk(
                        chunk_id="",
                        matter_id=matter_id,
                        document_id="",
                        source_page=legal_chunk.source_page,
                        chunk_index=len(chunks),
                        content=legal_chunk.content,
                    )
                )
            provenance.append(
                {
                    "document_role": "text_extraction",
                    "source_page": page.page_number,
                    "page_kind": "pdf_physical" if pages else "unknown",
                    "method": "native_pdf_text_layer" if pages else "local_document_parser",
                    "verification": VerificationStatus.TEXT_LAYER_VERIFIED.value,
                }
            )
            facts.append(
                {
                    "type": "extracted_text",
                    "source_page": page.page_number,
                    "verification": VerificationStatus.TEXT_LAYER_VERIFIED.value,
                }
            )

        return self.store.store_document(
            matter_id=matter_id,
            filename=filename,
            media_type=media_type,
            original_bytes=original_bytes,
            extracted_text=extracted_text,
            facts=tuple(facts),
            provenance=tuple(provenance),
            chunks=tuple(chunks),
        )
