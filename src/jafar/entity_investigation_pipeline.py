from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .legal_entity_adapters import LegalEntitySourceRegistry, SourceResult
from .legal_entity_intelligence import EntityQuery, LegalEntityIntelligence, SourceFinding


@dataclass(frozen=True, slots=True)
class InvestigationRun:
    query: EntityQuery
    results: tuple[SourceResult, ...]
    successful_sources: int
    failed_sources: int
    source_order: tuple[str, ...] = ()
    profile: dict[str, Any] = field(default_factory=dict)


class EntityInvestigationPipeline:
    """Runs registered entity sources and preserves per-source provenance.

    ``LegalEntitySourceRegistry`` is the canonical source boundary. A legacy
    iterable of ``lookup()`` sources is accepted for backwards compatibility so
    older callers can migrate without losing source attribution.
    """

    def __init__(
        self,
        registry: LegalEntitySourceRegistry | Iterable[Any],
    ) -> None:
        self.registry = registry

    def run(self, query: EntityQuery) -> InvestigationRun:
        normalized = query.normalized()
        results, findings = self._collect(normalized)
        successful = sum(1 for item in results if item.status in {"success", "found"})
        failed = sum(1 for item in results if item.status in {"error", "unavailable"})
        profile = LegalEntityIntelligence().build_profile(findings)
        return InvestigationRun(
            query=normalized,
            results=results,
            successful_sources=successful,
            failed_sources=failed,
            source_order=tuple(item.source_key for item in results),
            profile=profile,
        )

    def _collect(
        self,
        query: EntityQuery,
    ) -> tuple[tuple[SourceResult, ...], list[SourceFinding]]:
        if isinstance(self.registry, LegalEntitySourceRegistry):
            results = tuple(self.registry.search_all(query))
            findings = [self._result_to_finding(item) for item in results]
            return results, findings

        results: list[SourceResult] = []
        findings: list[SourceFinding] = []
        for source in self.registry:
            source_key = getattr(source, "source_key", type(source).__name__)
            try:
                finding = source.lookup(query)
            except Exception as exc:
                finding = SourceFinding(
                    source_key=source_key,
                    status="error",
                    title=source_key,
                    details={"reason": str(exc), "type": type(exc).__name__},
                )
            findings.append(finding)
            results.append(
                SourceResult(
                    source_key=finding.source_key,
                    status=finding.status,
                    source_url=finding.source_url,
                    data=finding.details,
                    error=(finding.details.get("reason") if finding.status == "error" else None),
                )
            )
        return tuple(results), findings

    @staticmethod
    def _result_to_finding(item: SourceResult) -> SourceFinding:
        return SourceFinding(
            source_key=item.source_key,
            status=item.status,
            title=item.source_key,
            details=item.data or {},
            source_url=item.source_url,
        )

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
