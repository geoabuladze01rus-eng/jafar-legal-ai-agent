from io import BytesIO

import pytest
from docx import Document
from pypdf import PdfWriter

from jafar.document_ingestion import UnsupportedDocumentError, ingest_document


def test_ingest_text_pdf_preserves_page_source() -> None:
    output = BytesIO()
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    from reportlab.pdfgen import canvas

    pdf_stream = BytesIO()
    canvas.Canvas(pdf_stream).drawString(50, 250, "Срок исполнения: 25.08.2026")
    canvas.Canvas(pdf_stream).save()
    # Build a valid PDF with extractable text using a tiny ReportLab document.
    output = pdf_stream.getvalue()
    document = ingest_document("notice.pdf", output)

    assert document.media_type == "application/pdf"
    assert "Срок исполнения" in document.text
    assert document.sources[0].page == 1
    assert not document.ocr_required


def test_ingest_docx() -> None:
    stream = BytesIO()
    doc = Document()
    doc.add_paragraph("Ходатайство о восстановлении процессуального срока.")
    doc.save(stream)

    document = ingest_document("petition.docx", stream.getvalue())

    assert document.media_type.startswith("application/vnd.openxmlformats")
    assert "восстановлении процессуального срока" in document.text
    assert len(document.sources) == 1


def test_scanned_pdf_is_marked_for_ocr() -> None:
    stream = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    writer.write(stream)

    document = ingest_document("scan.pdf", stream.getvalue())

    assert document.text == ""
    assert document.ocr_required


def test_unsupported_document_is_rejected() -> None:
    with pytest.raises(UnsupportedDocumentError):
        ingest_document("evidence.exe", b"not a legal document")
