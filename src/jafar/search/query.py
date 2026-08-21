from dataclasses import dataclass

from jafar.search.in_memory import InMemorySearch
from jafar.search.models import SearchResult


@dataclass(frozen=True)
class MatterSearchResult:
    results: list[SearchResult]
    total: int


def search_matter(search: InMemorySearch, query: str, limit: int = 10) -> MatterSearchResult:
    if not query.strip():
        return MatterSearchResult(results=[], total=0)
    results = search.search(query, limit=limit)
    return MatterSearchResult(results=results, total=len(results))
