from __future__ import annotations

from dataclasses import dataclass
import re

from .legal_models import Matter


RESEARCH_MARKERS = (
    "проанализируй", "анализ", "найди противореч", "противореч",
    "что следует", "что известно", "проверь дело", "исследуй",
    "сравни показан", "найди в деле", "по материалам дела",
)


@dataclass(frozen=True, slots=True)
class ResearchRoute:
    is_research: bool
    matter_id: str | None = None
    ambiguous: bool = False


class NaturalLanguageResearchRouter:
    """Conservative Russian-language routing for read-only matter research."""

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().replace("ё", "е").split())

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return set(re.findall(r"[а-яa-z0-9-]{4,}", value.casefold().replace("ё", "е")))

    def route(self, text: str, matters: list[Matter]) -> ResearchRoute:
        normalized = self._normalize(text)
        if not any(marker in normalized for marker in RESEARCH_MARKERS):
            return ResearchRoute(is_research=False)

        scored: list[tuple[int, str]] = []
        for matter in matters:
            score = 0
            case_number = self._normalize(matter.case_number or "")
            if case_number and case_number in normalized:
                score += 100

            for value in (matter.client_name, matter.title):
                if not value:
                    continue
                candidate = self._normalize(value)
                if candidate and candidate in normalized:
                    score += 50
                else:
                    overlap = self._tokens(value) & self._tokens(normalized)
                    score += min(20, 5 * len(overlap))

            if score:
                scored.append((score, matter.id))

        if not scored:
            return ResearchRoute(is_research=True)
        scored.sort(reverse=True)
        top_score = scored[0][0]
        top = [matter_id for score, matter_id in scored if score == top_score]
        if len(top) != 1 or top_score < 20:
            return ResearchRoute(is_research=True, ambiguous=True)
        return ResearchRoute(is_research=True, matter_id=top[0])
