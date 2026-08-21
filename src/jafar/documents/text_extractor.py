from dataclasses import dataclass
from pathlib import Path

from jafar.inbox.attachments import Attachment, AttachmentType, ExtractedAttachment


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    method: str
    confidence: float
    page_count: int | None = None


class DocumentTextExtractor:
    """Unified document-to-text boundary.

    Concrete PDF/DOCX/OCR adapters are injected at runtime so the legal
    pipeline does not depend on a particular parsing vendor.
    """

    def __init__(self, pdf=None, docx=None, ocr=None):
        self.pdf = pdf
        self.docx = docx
        self.ocr = ocr

    async def extract(self, attachment: Attachment, local_path: str) -> ExtractedAttachment:
        result = await self._extract(attachment.kind, local_path)
        return ExtractedAttachment(
            attachment=attachment,
            local_path=local_path,
            text=result.text,
            extraction_method=result.method,
            extraction_confidence=result.confidence,
        )

    async def _extract(self, kind: AttachmentType, local_path: str) -> ExtractionResult:
        path = Path(local_path)
        if kind is AttachmentType.PDF and self.pdf:
            return await self.pdf.extract(path)
        if kind is AttachmentType.DOCX and self.docx:
            return await self.docx.extract(path)
        if kind is AttachmentType.IMAGE and self.ocr:
            return await self.ocr.extract(path)
        return ExtractionResult("", "unsupported_or_missing_adapter", 0.0)
