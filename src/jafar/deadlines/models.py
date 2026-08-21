from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DeadlineCandidate:
    title: str
    due_at: datetime | None
    source_document_id: str | None = None
    source_chunk_id: str | None = None
    confidence: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class Deadline:
    deadline_id: str
    matter_id: str
    title: str
    due_at: datetime | None
    source_document_id: str | None
    status: str = "open"
