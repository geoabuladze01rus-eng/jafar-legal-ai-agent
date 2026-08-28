from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .legal_entity_adapters import LegalEntitySourceRegistry, SourceResult
from .legal_entity_intelligence import EntityQuery, LegalEntityIntelligence, SourceFinding


@dataclass(frozen=True)
class ResearchSource:
    key: str
    name: str
    category: str


DEFAULT_SOURCES = (
    ResearchSource("egrul", "ЕГРЮЛ / ФНС", "registration"),
    ResearchSource("checko", "Честный бизнес", "registration"),
    ResearchSource("kad", "Картотека арбитражных дел", "litigation"),
    ResearchSource("fssp", "ФССП / банк данных исполнительных производств", "enforcement"),
    ResearchSource("fedresurs", "Федресурс", "insolvency"),
    ResearchSource("bo", "Финансовая / бухгалтерская отчётность", "finance"),
    ResearchSource("disclosure", "Раскрытие корпоративной информации", "corporate"),
    ResearchSource("procurement", "Госзакупки / контракты", "procurement"),
    ResearchSource("open_web", "Открытые веб-источники", "web"),
)


@dataclass(frozen=True)
class ResearchReport:
    query: EntityQuery
    profile: dict[str, Any]
    results: tuple[SourceResult, ...]


class LegalEntityResearchService:
    """Runs registered public-source adapters and builds an auditable profile."""

    def __init__(
        self,
        registry: LegalEntitySourceRegistry | None = None,
        intelligence: LegalEntityIntelligence | None = None,
        persist: Callable[[EntityQuery, list[SourceResult], dict[str, Any]], None] | None = None,
    ) -> None:
        self.registry = registry or LegalEntitySourceRegistry()
        self.intelligence = intelligence or LegalEntityIntelligence()
        self.persist = persist

    def build_research_plan(self, query: EntityQuery) -> dict[str, Any]:
        return {
            "query": query.value,
            "query_type": query.query_type,
            "sources": [
                {"key": s.key, "name": s.name, "category": s.category}
                for s in DEFAULT_SOURCES
            ],
            "principles": [
                "use_publicly_available_information_only",
                "record_source_and_checked_at_for_every_finding",
                "distinguish_no_data_from_negative_finding",
                "preserve_source_urls_and_raw_structured_findings",
                "do_not_bypass_captcha_or_access_controls",
            ],
        }

    def research(self, query: EntityQuery) -> ResearchReport:
        results = self.registry.search_all(query)
        findings = [
            SourceFinding(
                source_key=result.source_key,
                status=result.status,
                title=result.source_key,
                details=result.data or {},
                source_url=result.source_url,
            )
            for result in results
        ]
        # These findings crossed the server-owned adapter registry and its source/status/URL
        # validation boundary. Caller-supplied findings use trusted=False at the HTTP API.
        profile = self.intelligence.build_profile(findings, trusted=True)
        if self.persist:
            self.persist(query, results, profile)
        return ResearchReport(query=query, profile=profile, results=tuple(results))

    def merge_findings(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "sources_checked": len(findings),
            "sources": findings,
            "has_negative_findings": any(
                item.get("status") == "negative" for item in findings
            ),
            "has_errors": any(item.get("status") == "error" for item in findings),
        }
