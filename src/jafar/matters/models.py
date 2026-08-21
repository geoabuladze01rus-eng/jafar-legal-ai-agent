from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Matter:
    matter_id: str
    title: str
    matter_type: str
    status: str = "active"
    client_id: str | None = None
    case_number: str | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class NewMatterCandidate:
    title: str
    matter_type: str
    client_name: str | None
    source_message_id: str | None
    confidence: float
    requires_approval: bool = True
