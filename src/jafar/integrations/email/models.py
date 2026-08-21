from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class EmailAttachment:
    attachment_id: str
    filename: str
    content_type: str
    size: int | None = None


@dataclass(frozen=True)
class LegalEmail:
    message_id: str
    sender: str
    subject: str
    received_at: datetime
    body_preview: str
    has_attachments: bool = False
    attachments: list[EmailAttachment] = field(default_factory=list)


@dataclass(frozen=True)
class EmailTriageResult:
    is_legal_relevant: bool
    confidence: float
    reasons: list[str] = field(default_factory=list)
    suggested_matter_id: str | None = None
