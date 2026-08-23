from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class SourceQuery:
    name: str | None = None
    inn: str | None = None
    ogrn: str | None = None
    kpp: str | None = None


@dataclass(frozen=True, slots=True)
class SourceResult:
    source: str
    status: str
    data: dict[str, Any]
    error: str | None = None


class SourceAdapter(Protocol):
    name: str

    def collect(self, query: SourceQuery) -> SourceResult: ...


class SourceCollector:
    """Runs independent public/free-source adapters without failing the whole investigation."""

    def __init__(self, adapters: list[SourceAdapter]) -> None:
        self.adapters = adapters

    def collect(self, query: SourceQuery) -> list[SourceResult]:
        if not self.adapters:
            return []
        results: list[SourceResult] = []
        with ThreadPoolExecutor(max_workers=min(8, len(self.adapters))) as pool:
            futures = {pool.submit(adapter.collect, query): adapter for adapter in self.adapters}
            for future in as_completed(futures):
                adapter = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:  # noqa: BLE001 - collector isolates adapter failures
                    results.append(SourceResult(adapter.name, "error", {}, str(exc)))
        return sorted(results, key=lambda item: item.source)
