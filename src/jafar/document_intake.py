from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .document_parsers import (
    DocumentParser,
    DocumentParserError,
    NativeDocumentParser,
    build_document_parser,
)


@dataclass(frozen=True)
class ExtractedDocument:
    filename: str
    media_type: str
    text: str

    @property
    def fingerprint(self) -> str:
        """Stable identity for the extracted document content."""
        payload = f"{self.media_type}\n{self.text}".encode("utf-8")
        return sha256(payload).hexdigest()


class DocumentExtractionError(ValueError):
    pass


class DocumentExtractor:
    """Extract text from legal documents through a replaceable parser provider.

    The default remains the dependency-light native parser for backwards compatibility.
    Set ``prefer_docling=True`` (or inject a parser) to use local layout-aware parsing with
    automatic native fallback.
    """

    MAX_BYTES = 20 * 1024 * 1024
    SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx"}

    def __init__(
        self,
        parser: DocumentParser | None = None,
        *,
        prefer_docling: bool = False,
    ) -> None:
        self.parser = parser or build_document_parser(prefer_docling=prefer_docling)

    def extract(
        self,
        filename: str,
        content: bytes,
        media_type: str | None = None,
    ) -> ExtractedDocument:
        if len(content) > self.MAX_BYTES:
            raise DocumentExtractionError("Document exceeds the 20 MB limit")
        extension = Path(filename).suffix.lower()
        if not self.parser.supports(filename, media_type):
            raise DocumentExtractionError(f"Unsupported document format: {extension or 'unknown'}")
        try:
            text = self.parser.parse(filename, content, media_type)
        except DocumentParserError as exc:
            raise DocumentExtractionError(str(exc)) from exc
        text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
        if not text:
            raise DocumentExtractionError("No text could be extracted from the document")
        return ExtractedDocument(
            filename=filename,
            media_type=media_type or "application/octet-stream",
            text=text,
        )

    @staticmethod
    def _extract_pdf(content: bytes) -> str:
        """Compatibility shim for callers using the former private helper."""
        try:
            return NativeDocumentParser._extract_pdf(content)
        except DocumentParserError as exc:
            raise DocumentExtractionError(str(exc)) from exc

    @staticmethod
    def _extract_docx(content: bytes) -> str:
        """Compatibility shim for callers using the former private helper."""
        try:
            return NativeDocumentParser._extract_docx(content)
        except DocumentParserError as exc:
            raise DocumentExtractionError(str(exc)) from exc
