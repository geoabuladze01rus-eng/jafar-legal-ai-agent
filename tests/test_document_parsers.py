from types import SimpleNamespace

import pytest

from jafar.document_intake import DocumentExtractor
from jafar.document_parsers import (
    DoclingDocumentParser,
    DocumentParserError,
    FallbackDocumentParser,
    NativeDocumentParser,
)


class FakeDocument:
    def export_to_markdown(self):
        return "# Постановление\n\nСуд установил обстоятельства дела."


class FakeConverter:
    def __init__(self):
        self.source = None
        self.max_file_size = None

    def convert(self, source, *, max_file_size):
        self.source = source
        self.max_file_size = max_file_size
        return SimpleNamespace(document=FakeDocument())


class FakeStream:
    def __init__(self, *, name, stream):
        self.name = name
        self.stream = stream


class FailingParser:
    def supports(self, filename, media_type=None):
        return filename.endswith(".txt")

    def parse(self, filename, content, media_type=None):
        raise DocumentParserError("primary failed")


def test_docling_parser_uses_in_memory_document_stream():
    converter = FakeConverter()
    parser = DoclingDocumentParser(converter=converter, stream_factory=FakeStream)

    text = parser.parse("ruling.pdf", b"pdf-bytes", "application/pdf")

    assert text.startswith("# Постановление")
    assert converter.source.name == "ruling.pdf"
    assert converter.source.stream.read() == b"pdf-bytes"
    assert converter.max_file_size == len(b"pdf-bytes")


def test_docling_supports_rich_office_formats():
    parser = DoclingDocumentParser(converter=FakeConverter(), stream_factory=FakeStream)

    assert parser.supports("case.pdf")
    assert parser.supports("evidence.xlsx")
    assert parser.supports("slides.pptx")
    assert not parser.supports("scan.png")


def test_fallback_parser_preserves_native_behavior_when_primary_fails():
    parser = FallbackDocumentParser(primary=FailingParser(), fallback=NativeDocumentParser())

    text = parser.parse("petition.txt", "Ходатайство".encode("utf-8"), "text/plain")

    assert text == "Ходатайство"


def test_document_extractor_accepts_injected_docling_parser():
    parser = DoclingDocumentParser(converter=FakeConverter(), stream_factory=FakeStream)
    result = DocumentExtractor(parser=parser).extract("ruling.pdf", b"pdf-bytes", "application/pdf")

    assert "Суд установил" in result.text


def test_docling_dependency_error_is_explicit(monkeypatch):
    parser = DoclingDocumentParser()

    def unavailable():
        raise DocumentParserError("Docling support is not installed")

    monkeypatch.setattr(parser, "_build_converter", unavailable)

    with pytest.raises(DocumentParserError, match="Docling support"):
        parser.parse("ruling.pdf", b"pdf-bytes")
