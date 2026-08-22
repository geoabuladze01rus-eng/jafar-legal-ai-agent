from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .legal_entity_adapters import LegalEntitySourceRegistry, SourceResult
from .legal_entity_intelligence import EntityQuery


@dataclass(frozen=True, slots=True)
class InvestigationRun:
    query: EntityQuery
    results: tuple[SourceResult, ...]
    successful_sources: int
    failed_sources: int


class EntityInvestigationPipeline:
    """Runs all registered entity sources and preserves per-source provenance."""

    def __init__(self, registry: LegalEntitySourceRegistry) -> None:
        self.registry = registry

    def run(self, query: EntityQuery) -> InvestigationRun:
        results = tuple(self.registry.search_all(query))
        successful = sum(1 for item in results if item.status in {"success", "found"})
        failed = sum(1 for item in results if item.status in {"error", "unavailable"})
        return InvestigationRun(query, results, successful, failed)

    @staticmethod
    def to_report_input(run: InvestigationRun) -> list[dict[str, Any]]:
        return [
            {
                "source": item.source_key,
                "status": item.status,
                "source_url": item.source_url,
                "result": item.data or {},
                "error": item.error,
            }
            for item in run.results
        ]
