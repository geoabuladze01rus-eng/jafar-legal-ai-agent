from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .legal_entity_intelligence import EntityQuery, EntitySource, LegalEntityIntelligence


@dataclass(frozen=True, slots=True)
class InvestigationReport:
    query: EntityQuery
    profile: dict[str, Any]
    source_order: tuple[str, ...]


class EntityInvestigationPipeline:
    """Runs the configured public/free-source entity checks as one auditable job."""

    def __init__(self, sources: list[EntitySource]) -> None:
        self.sources = sources
        self.engine = LegalEntityIntelligence(sources)

    def run(self, query: EntityQuery) -> InvestigationReport:
        normalized = query.normalized()
        profile = self.engine.investigate(normalized)
        return InvestigationReport(
            query=normalized,
            profile=profile,
            source_order=tuple(source.source_key for source in self.sources),
        )

    @staticmethod
    def to_dict(report: InvestigationReport) -> dict[str, Any]:
        return {
            "query": {
                "name": report.query.name,
                "inn": report.query.inn,
                "ogrn": report.query.ogrn,
                "kpp": report.query.kpp,
            },
            "source_order": list(report.source_order),
            "profile": report.profile,
        }
