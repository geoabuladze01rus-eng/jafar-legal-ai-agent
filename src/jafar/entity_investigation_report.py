from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EntityInvestigationReport:
    subject: dict[str, Any]
    registry: dict[str, Any]
    sources: tuple[dict[str, Any], ...]
    risks: tuple[dict[str, Any], ...]
    checked_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "registry": self.registry,
            "sources": list(self.sources),
            "risks": list(self.risks),
            "checked_at": self.checked_at,
        }


class EntityInvestigationReportBuilder:
    """Builds an auditable legal-entity report from normalized source results."""

    def build(self, *, subject: dict[str, Any], registry: dict[str, Any], source_results: list[dict[str, Any]], risks: list[dict[str, Any]], checked_at: str) -> EntityInvestigationReport:
        ordered = tuple(sorted(source_results, key=lambda item: str(item.get("source", ""))))
        return EntityInvestigationReport(subject, registry, ordered, tuple(risks), checked_at)
