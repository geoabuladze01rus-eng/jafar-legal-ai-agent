from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .legal_entity_adapters import LegalEntitySourceRegistry, SourceResult
from .legal_entity_intelligence import EntityQuery, LegalEntityIntelligence, SourceFinding


@dataclass(frozen=True, slots=True)
class InvestigationRun:
    query: EntityQuery
    results: tuple[SourceResult, ...]
    successful_sources: int
    failed_sources: int
    profile: dict[str, Any] | None = None

    @property
    def source_order(self) -> tuple[str, ...]:
        return tuple(item.source_key for item in self.results)


class EntityInvestigationPipeline:
    """Runs all registered entity sources and preserves per-source provenance."""

    def __init__(self, registry: LegalEntitySourceRegistry | Sequence[Any]) -> None:
        self.registry = registry

    def run(self, query: EntityQuery) -> InvestigationRun:
        if isinstance(self.registry, LegalEntitySourceRegistry):
            results = tuple(self.registry.search_all(query))
            profile = None
        else:
            findings: list[SourceFinding] = []
            for source in self.registry:
                try:
                    findings.append(source.lookup(query))
                except Exception as exc:  # noqa: BLE001
                    findings.append(
                        SourceFinding(
                            source.source_key,
                            "error",
                            source.source_key,
                            {"error": type(exc).__name__},
                        )
                    )
            results = tuple(
                SourceResult(
                    source_key=item.source_key,
                    status=item.status,
                    source_url=item.source_url,
                    data=item.details,
                    error=None if item.status != "error" else item.details.get("error"),
                )
                for item in findings
            )
            profile = LegalEntityIntelligence().build_profile(findings, trusted=True)
        successful = sum(1 for item in results if item.status in {"success", "found"})
        failed = sum(1 for item in results if item.status in {"error", "unavailable"})
        return InvestigationRun(query, results, successful, failed, profile)

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
