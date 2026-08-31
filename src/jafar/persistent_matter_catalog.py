from __future__ import annotations

from dataclasses import dataclass
import re

from .matter_repository import MatterRepository
from .natural_language_research import NaturalLanguageResearchRouter, ResearchRoute


@dataclass(frozen=True, slots=True)
class MatterReference:
    matter_id: str | None = None
    ambiguous: bool = False


class PersistentMatterCatalog:
    """Resolve natural-language matter references from persistent repository state."""

    def __init__(self, repository: MatterRepository, router: NaturalLanguageResearchRouter | None = None) -> None:
        self.repository = repository
        self.router = router or NaturalLanguageResearchRouter()

    def route(self, text: str) -> ResearchRoute:
        return self.router.route(text, self.repository.list_matters())

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().replace("ё", "е").split())

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return set(re.findall(r"[а-яa-z0-9-]{4,}", value.casefold().replace("ё", "е")))

    def resolve_reference(self, text: str) -> MatterReference:
        """Resolve an optional matter reference without requiring a research marker."""
        normalized = self._normalize(text)
        scored: list[tuple[int, str]] = []
        for matter in self.repository.list_matters():
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
                    score += min(20, 5 * len(self._tokens(value) & self._tokens(normalized)))
            if score:
                scored.append((score, matter.id))

        if not scored:
            return MatterReference()
        scored.sort(reverse=True)
        top_score = scored[0][0]
        top = [matter_id for score, matter_id in scored if score == top_score]
        if len(top) != 1 or top_score < 20:
            return MatterReference(ambiguous=True)
        return MatterReference(matter_id=top[0])
