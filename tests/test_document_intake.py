import pytest

from jafar.document_intake import DocumentExtractionError, DocumentExtractor


def test_extracts_utf8_text():
    result = DocumentExtractor().extract("petition.txt", "Ходатайство суда".encode(), "text/plain")
    assert result.filename == "petition.txt"
    assert result.text == "Ходатайство суда"


def test_non_pdf_page_contract_uses_single_source_page():
    pages = DocumentExtractor().extract_pages(
        "petition.txt",
        "Первая строка\nВторая строка".encode(),
        "text/plain",
    )

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].text == "Первая строка\nВторая строка"


def test_rejects_unsupported_format():
    with pytest.raises(DocumentExtractionError, match="Unsupported document format"):
        DocumentExtractor().extract("photo.png", b"data", "image/png")


def test_rejects_empty_document():
    with pytest.raises(DocumentExtractionError, match="No text"):
        DocumentExtractor().extract("empty.txt", b"   ", "text/plain")


def test_rejects_documents_over_20_mb():
    content = b"x" * (DocumentExtractor.MAX_BYTES + 1)
    with pytest.raises(DocumentExtractionError, match="20 MB"):
        DocumentExtractor().extract("large.txt", content, "text/plain")
