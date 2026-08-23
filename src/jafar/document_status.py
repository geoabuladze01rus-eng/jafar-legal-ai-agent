from __future__ import annotations

from enum import StrEnum


class DocumentStatus(StrEnum):
    STORED = "stored"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
