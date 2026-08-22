from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

from .legal_entity_intelligence import EntityQuery


@dataclass(slots=True)
class SourceResult:
    source_key: str
    status: str
    source_url: str | None = None
    data: dict[str, Any] | None = None
    error: str | None = None


class LegalEntitySource(Protocol):
    source_key: str

    def search(self, query: EntityQuery) -> SourceResult: ...


class PublicSourceAdapter:
    """Safe adapter contract for a public source.

    Concrete adapters must use only documented/public endpoints and must not
    bypass authentication, CAPTCHA, robots controls, paywalls, or other access
    restrictions. Network transport is intentionally injected by the caller.
    """

    def __init__(self, source_key: str, source_url: str | None = None) -> None:
        self.source_key = source_key
        self.source_url = source_url

    def search(self, query: EntityQuery) -> SourceResult:
        return SourceResult(
            source_key=self.source_key,
            status="no_data",
            source_url=self.source_url,
            data={"query": query.value, "query_type": query.query_type},
        )


class PublicUrlSourceAdapter(PublicSourceAdapter):
    """Builds a deterministic public-search URL without performing network I/O."""

    def __init__(self, source_key: str, search_url_template: str) -> None:
        super().__init__(source_key)
        self.search_url_template = search_url_template

    def search(self, query: EntityQuery) -> SourceResult:
        url = self.search_url_template.format(query=quote(query.value, safe=""))
        return SourceResult(
            source_key=self.source_key,
            status="no_data",
            source_url=url,
            data={
                "query": query.value,
                "query_type": query.query_type,
                "transport": "not_configured",
            },
        )


class KadPublicAdapter(PublicUrlSourceAdapter):
    """KAD adapter boundary; transport remains injected and policy-controlled."""

    def __init__(self, search_url_template: str) -> None:
        super().__init__("kad", search_url_template)


class LegalEntitySourceRegistry:
    def __init__(self, adapters: list[LegalEntitySource] | None = None) -> None:
        self._adapters: dict[str, LegalEntitySource] = {
            adapter.source_key: adapter for adapter in (adapters or [])
        }

    def register(self, adapter: LegalEntitySource) -> None:
        self._adapters[adapter.source_key] = adapter

    def keys(self) -> list[str]:
        return sorted(self._adapters)

    def search_all(self, query: EntityQuery) -> list[SourceResult]:
        results: list[SourceResult] = []
        for adapter in self._adapters.values():
            try:
                results.append(adapter.search(query))
            except Exception as exc:
                results.append(
                    SourceResult(
                        source_key=adapter.source_key,
                        status="error",
                        error=str(exc),
                    )
                )
        return results
