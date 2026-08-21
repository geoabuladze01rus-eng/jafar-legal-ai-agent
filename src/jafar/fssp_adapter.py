from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .legal_entity_adapters import SourceResult
from .legal_entity_intelligence import EntityQuery
from .public_source_transport import SafePublicSourceTransport


@dataclass(frozen=True, slots=True)
class FsspResponseParser:
    """Conservative parser boundary for public FSSP/IPD responses."""

    def parse(self, text: str) -> dict[str, Any]:
        return {"raw_text": text}


class FsspPublicAdapter:
    source_key = "fssp"

    def __init__(self, transport: SafePublicSourceTransport, url_builder: Callable[[EntityQuery], str], parser: FsspResponseParser | None = None) -> None:
        self.transport = transport
        self.url_builder = url_builder
        self.parser = parser or FsspResponseParser()

    def search(self, query: EntityQuery) -> SourceResult:
        try:
            url = self.url_builder(query)
            response = self.transport.get(url)
            return SourceResult(
                source_key=self.source_key,
                status="found",
                source_url=response.url,
                data=self.parser.parse(response.text),
            )
        except Exception as exc:
            return SourceResult(source_key=self.source_key, status="error", error=str(exc))
