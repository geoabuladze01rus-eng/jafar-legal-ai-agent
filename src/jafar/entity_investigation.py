from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InvestigationSource:
    source_type: str
    source_name: str
    query: str
    status: str = "pending"


class EntityInvestigation:
    """Builds a multi-source investigation plan for a Russian legal entity."""

    SOURCES = (
        ("fns_egrul", "ФНС / ЕГРЮЛ"),
        ("fssp", "ФССП / банк исполнительных производств"),
        ("kad", "Картотека арбитражных дел"),
        ("fedresurs", "Федресурс"),
        ("checko", "Честный бизнес / открытые сведения"),
        ("financial_reporting", "Открытая финансовая отчётность"),
    )

    def plan(self, *, query: str, inn: str | None = None, ogrn: str | None = None, name: str | None = None) -> list[InvestigationSource]:
        target = ogrn or inn or name or query
        return [InvestigationSource(source_type, source_name, target) for source_type, source_name in self.SOURCES]

    @staticmethod
    def merge_results(results: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "sources_checked": len(results),
            "successful_sources": sum(1 for item in results if item.get("status") == "success"),
            "results": results,
        }
