"""Physical PDF page provenance is never inferred from flattened text."""

from __future__ import annotations

import pytest

from jafar.desktop_corpus_service import DesktopCorpusService
from jafar.document_intake import DocumentExtractor
from jafar.document_parsers import NativeDocumentParser, ParsedPage
from jafar.encrypted_desktop_corpus import EncryptedDesktopCorpusStore


def _store(tmp_path):
    return EncryptedDesktopCorpusStore(
        tmp_path / "corpus.sqlite3", tmp_path / "documents", b"p" * 32
    )


def test_native_pdf_parser_passes_true_page_boundaries_to_extractor(monkeypatch):
    pages = (
        ParsedPage(1, "Дата договора: 01.01.2026"),
        ParsedPage(2, ""),
        ParsedPage(3, "Сумма договора: 1 000 000 руб."),
    )
    monkeypatch.setattr(
        NativeDocumentParser, "_extract_pdf_pages",
        staticmethod(lambda content: pages),
    )
    extracted = DocumentExtractor().extract("contract.pdf", b"%PDF-synthetic")
    assert extracted.pages == pages
    assert "Дата договора" in extracted.text
    assert "Сумма договора" in extracted.text


def test_pdf_index_keeps_actual_physical_page_three_and_no_cross_page_chunk(tmp_path):
    store = _store(tmp_path)
    pages = (
        ParsedPage(1, "Дата договора: 01.01.2026"),
        ParsedPage(2, ""),
        ParsedPage(3, "Сумма договора: 1 000 000 руб."),
    )
    text = "\n".join(page.text for page in pages)
    document = DesktopCorpusService(store).import_document(
        matter_id="matter-a", filename="contract.pdf",
        media_type="application/pdf", original_bytes=b"%PDF TEST ONLY",
        extracted_text=text, pages=pages,
    )
    chunks = store.chunks("matter-a")
    assert {chunk.source_page for chunk in chunks} == {1, 3}
    assert "page:1:chunk" in chunks[0].citation
    assert "page:3:chunk" in chunks[-1].citation
    assert chunks[0].chunk_index != chunks[-1].chunk_index
    assert document.provenance[0]["page_kind"] == "pdf_physical"
    assert [item["source_page"] for item in document.provenance] == [1, 2, 3]
    assert all(item["verification"] == "text_layer_verified" for item in document.provenance)
    store.close()


def test_non_pdf_citations_have_unknown_location(tmp_path):
    store = _store(tmp_path)
    document = DesktopCorpusService(store).import_document(
        matter_id="matter-a", filename="synthetic.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        original_bytes=b"FAKE DOCX CONTENT",
        extracted_text="Синтетическая позиция для сверки.",
    )
    result = store.chunks("matter-a")
    assert len(result) == 1
    assert result[0].source_page == 0
    assert document.provenance[0]["page_kind"] == "unknown"
    store.close()


def test_page_mismatch_or_fake_non_pdf_page_metadata_fails_without_persisting(tmp_path):
    store = _store(tmp_path)
    service = DesktopCorpusService(store)
    with pytest.raises(ValueError, match="does not match"):
        service.import_document(
            matter_id="matter-a", filename="contract.pdf",
            media_type="application/pdf", original_bytes=b"%PDF synthetic",
            extracted_text="One",
            pages=[ParsedPage(1, "Different")],
        )
    with pytest.raises(ValueError, match="only for native PDF"):
        service.import_document(
            matter_id="matter-a", filename="text.txt",
            media_type="text/plain", original_bytes=b"TEXT",
            extracted_text="Text",
            pages=[ParsedPage(1, "Text")],
        )
    assert store.documents("matter-a") == []
    store.close()


def test_missing_or_duplicate_page_number_not_silently_accepted(tmp_path):
    store = _store(tmp_path)
    service = DesktopCorpusService(store)
    with pytest.raises(ValueError, match="unique and sequential"):
        service.import_document(
            matter_id="matter-a", filename="contract.pdf",
            media_type="application/pdf", original_bytes=b"%PDF synthetic",
            extracted_text="One\nTwo",
            pages=[ParsedPage(1, "One"), ParsedPage(1, "Two")],
        )
    store.close()


def test_unverified_custom_parser_does_not_claim_pdf_page_provenance():
    class ExternalParser:
        def supports(self, filename, media_type=None):
            return True

        def parse(self, filename, content, media_type=None):
            return "Сумма договора: 900 000 руб."

    extracted = DocumentExtractor(parser=ExternalParser()).extract(
        "contract.pdf", b"dummy external PDF"
    )
    assert extracted.pages == ()


def test_swift_page_label_and_server_schema_degrade_legacy_documents_to_unknown():
    from pathlib import Path

    root = Path(__file__).parents[1]
    api = (root / "apple/JafarApp/JusticiaAPIClient.swift").read_text(encoding="utf-8")
    assistant = (root / "apple/JafarApp/JusticiaMatterAssistantView.swift").read_text(
        encoding="utf-8"
    )
    main = (root / "src/jafar/main.py").read_text(encoding="utf-8")
    assert "pageProvenance" in api
    assert "page_provenance" in api
    assert "pages=extracted.pages" in main
    assert 'record.get("page_kind") == "pdf_physical"' in main
    assert 'return "unknown"' in main
    assert "hasPhysicalPDFPage" in assistant
    assert "Страница не установлена" in assistant
    assert "страница не установлена" in assistant
