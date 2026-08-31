from __future__ import annotations

from .matter_repository import MatterRepository
from .natural_language_research import NaturalLanguageResearchRouter, ResearchRoute


class PersistentMatterCatalog:
    """Resolve natural-language matter references from persistent repository state."""

    def __init__(self, repository: MatterRepository, router: NaturalLanguageResearchRouter | None = None) -> None:
        self.repository = repository
        self.router = router or NaturalLanguageResearchRouter()

    def route(self, text: str) -> ResearchRoute:
        return self.router.route(text, self.repository.list_matters())
