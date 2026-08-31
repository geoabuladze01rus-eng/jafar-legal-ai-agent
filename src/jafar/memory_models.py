from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MemoryKind(str, Enum):
    PREFERENCE = "preference"
    DECISION = "decision"
    FACT = "fact"
    WORKFLOW = "workflow"
    NOTE = "note"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    id: str
    owner_user_id: str
    kind: MemoryKind
    content: str
    created_at: datetime
    matter_id: str | None = None
    source: str | None = None
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class MemorySearchResult:
    memory: MemoryRecord
    similarity: float
