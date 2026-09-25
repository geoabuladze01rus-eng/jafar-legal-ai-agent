"""Explicit local document import into the encrypted desktop corpus."""

from __future__ import annotations

from .case_acceptance import VerificationStatus
from .encrypted_desktop_corpus import CorpusDocument, EncryptedDesktopCorpusStore
from .legal_chunking import semantic_legal_chunks
from .matter_rag import MatterChunk


class DesktopCorpusService:
    def __init__(self, store: EncryptedDesktopCorpusStore) -> None:
        self.store = store

    def import_document(
        self, *, matter_id: str, filename: str, media_type: str, original_bytes: bytes, extracted_text: str
    ) -> CorpusDocument:
        legal_chunks = semantic_legal_chunks(extracted_text, source_page=1)
        chunks = tuple(
            MatterChunk(
                chunk_id="", matter_id=matter_id, document_id="", source_page=item.source_page,
                chunk_index=index, content=item.content,
            )
            for index, item in enumerate(legal_chunks)
        )
        provenance = ({
            "document_role": "text_extraction", "source_page": 1,
            "method": "local_document_parser",
            "verification": VerificationStatus.TEXT_LAYER_VERIFIED.value,
        },)
        facts = ({
            "type": "extracted_text", "source_page": 1,
            "verification": VerificationStatus.TEXT_LAYER_VERIFIED.value,
        },)
        return self.store.store_document(
            matter_id=matter_id, filename=filename, media_type=media_type,
            original_bytes=original_bytes, extracted_text=extracted_text,
            facts=facts, provenance=provenance, chunks=chunks,
        )
