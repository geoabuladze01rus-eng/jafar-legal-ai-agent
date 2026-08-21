import re
from collections import Counter

from jafar.search.models import IndexedChunk, SearchResult


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w\-№§]+", text.lower(), flags=re.UNICODE)


class InMemorySearch:
    """Deterministic lexical search used until persistent/vector search is configured."""

    def __init__(self) -> None:
        self._chunks: dict[str, IndexedChunk] = {}

    def add(self, chunk: IndexedChunk) -> None:
        self._chunks[chunk.chunk_id] = chunk

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        query_tokens = Counter(_tokens(query))
        if not query_tokens:
            return []

        results: list[SearchResult] = []
        for chunk in self._chunks.values():
            tokens = Counter(_tokens(chunk.text))
            overlap = sum(min(count, tokens[token]) for token, count in query_tokens.items())
            if overlap == 0:
                continue
            score = overlap / max(sum(query_tokens.values()), 1)
            results.append(SearchResult(chunk.chunk_id, chunk.text, chunk.source, score))

        return sorted(results, key=lambda item: (-item.score, item.chunk_id))[:limit]
