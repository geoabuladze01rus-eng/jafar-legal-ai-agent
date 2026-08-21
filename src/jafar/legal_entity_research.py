from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EntityQuery:
    value: str
    query_type: str


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


class LegalEntityResearchService:
    """Orchestrates public-source legal-entity due diligence.

    Network adapters are deliberately separated from orchestration so that each
    public source can be implemented, tested and disabled independently. The
    service never treats missing source data as proof of absence.
    """

    def __init__(self, sources: tuple[ResearchSource, ...] = DEFAULT_SOURCES) -> None:
        self.sources = sources

    def build_research_plan(self, query: EntityQuery) -> dict[str, Any]:
        return {
            "query": query.value,
            "query_type": query.query_type,
            "sources": [
                {"key": s.key, "name": s.name, "category": s.category}
                for s in self.sources
            ],
            "principles": [
                "use_publicly available information only",
                "record source and checked_at for every finding",
                "distinguish no_data from negative_finding",
                "preserve source URLs and raw structured findings",
                "do_not_bypass_captcha_or_access_controls",
            ],
        }

    def merge_findings(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "sources_checked": len(findings),
            "sources": findings,
            "has_negative_findings": any(
                item.get("status") == "negative" for item in findings
            ),
            "has_errors": any(item.get("status") == "error" for item in findings),
        }
