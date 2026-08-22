from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SourceResult:
    source_type: str
    source_name: str
    status: str
    result: dict[str, Any]
    source_url: str | None = None
    confidence: float = 0.0


class EntitySourceContract:
    """Common adapter result contract; unavailable sources must remain explicit."""

    @staticmethod
    def success(source_type: str, source_name: str, result: dict[str, Any], source_url: str | None = None, confidence: float = 1.0) -> SourceResult:
        return SourceResult(source_type, source_name, "success", result, source_url, confidence)

    @staticmethod
    def unavailable(source_type: str, source_name: str, reason: str, source_url: str | None = None) -> SourceResult:
        return SourceResult(source_type, source_name, "unavailable", {"reason": reason}, source_url, 0.0)

    @staticmethod
    def error(source_type: str, source_name: str, reason: str, source_url: str | None = None) -> SourceResult:
        return SourceResult(source_type, source_name, "error", {"reason": reason}, source_url, 0.0)
