from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path


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
    """Extract text from legal documents supported by Jafar."""

    MAX_BYTES = 20 * 1024 * 1024
    SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx"}

    def extract(self, filename: str, content: bytes, media_type: str | None = None) -> ExtractedDocument:
        if len(content) > self.MAX_BYTES:
            raise DocumentExtractionError("Document exceeds the 20 MB limit")
        extension = Path(filename).suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise DocumentExtractionError(f"Unsupported document format: {extension or 'unknown'}")
        if extension in {".txt", ".md", ".markdown"}:
            text = content.decode("utf-8-sig", errors="replace")
        elif extension == ".pdf":
            text = self._extract_pdf(content)
        else:
            text = self._extract_docx(content)
        text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
        if not text:
            raise DocumentExtractionError("No text could be extracted from the document")
        return ExtractedDocument(filename=filename, media_type=media_type or "application/octet-stream", text=text)

    @staticmethod
    def _extract_pdf(content: bytes) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise DocumentExtractionError("PDF support is not installed") from exc
        try:
            reader = PdfReader(BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise DocumentExtractionError("Unable to read PDF document") from exc

    @staticmethod
    def _extract_docx(content: bytes) -> str:
        try:
            from docx import Document
        except ImportError as exc:
            raise DocumentExtractionError("DOCX support is not installed") from exc
        try:
            document = Document(BytesIO(content))
            paragraphs = [paragraph.text for paragraph in document.paragraphs]
            for table in document.tables:
                for row in table.rows:
                    paragraphs.append(" | ".join(cell.text for cell in row.cells))
            return "\n".join(paragraphs)
        except Exception as exc:
            raise DocumentExtractionError("Unable to read DOCX document") from exc
