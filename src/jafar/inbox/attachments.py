from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class AttachmentType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    IMAGE = "image"
    OTHER = "other"


@dataclass(frozen=True)
class Attachment:
    attachment_id: str
    message_id: str
    filename: str
    mime_type: str
    size_bytes: int
    kind: AttachmentType


@dataclass(frozen=True)
class ExtractedAttachment:
    attachment: Attachment
    local_path: str
    text: str
    extraction_method: str
    extraction_confidence: float


def detect_attachment_type(filename: str, mime_type: str) -> AttachmentType:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf" or mime_type == "application/pdf":
        return AttachmentType.PDF
    if ext == ".docx" or mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return AttachmentType.DOCX
    if mime_type.startswith("image/") or ext in {".jpg", ".jpeg", ".png", ".heic", ".tiff"}:
        return AttachmentType.IMAGE
    return AttachmentType.OTHER


def make_attachment(
    attachment_id: str,
    message_id: str,
    filename: str,
    mime_type: str,
    size_bytes: int,
) -> Attachment:
    return Attachment(
        attachment_id=attachment_id,
        message_id=message_id,
        filename=filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        kind=detect_attachment_type(filename, mime_type),
    )
