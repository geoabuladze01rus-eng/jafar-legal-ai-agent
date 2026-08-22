from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EntityReport:
    query: str
    identity: dict[str, Any]
    source_results: tuple[dict[str, Any], ...]
    risk_flags: tuple[str, ...]
    confidence: float


class EntityReportEngine:
    """Normalizes multi-source entity checks into a single lawyer-readable report."""

    def build(self, *, query: str, source_results: list[dict[str, Any]]) -> EntityReport:
        identity: dict[str, Any] = {}
        risks: list[str] = []
        confidences: list[float] = []
        for item in source_results:
            result = item.get("result") or {}
            if isinstance(result, dict):
                for key in ("name", "inn", "ogrn", "status", "address"):
                    if result.get(key) and key not in identity:
                        identity[key] = result[key]
                risks.extend(str(flag) for flag in result.get("risk_flags", []) if flag)
            if isinstance(item.get("confidence"), (int, float)):
                confidences.append(float(item["confidence"]))
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return EntityReport(query, identity, tuple(source_results), tuple(dict.fromkeys(risks)), confidence)
