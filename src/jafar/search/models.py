from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    text: str
    source: str
    score: float


@dataclass(frozen=True)
class IndexedChunk:
    chunk_id: str
    text: str
    source: str
