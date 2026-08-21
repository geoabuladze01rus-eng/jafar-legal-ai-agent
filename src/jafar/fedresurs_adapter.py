from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .legal_entity_adapters import SourceResult
from .legal_entity_intelligence import EntityQuery
from .public_source_transport import SafePublicSourceTransport


@dataclass(frozen=True, slots=True)
class FedresursResponseParser:
    def parse(self, text: str) -> dict[str, Any]:
        return {"raw_text": text}


class FedresursPublicAdapter:
    source_key = "fedresurs"

    def __init__(self, transport: SafePublicSourceTransport, url_builder: Callable[[EntityQuery], str], parser: FedresursResponseParser | None = None) -> None:
        self.transport = transport
        self.url_builder = url_builder
        self.parser = parser or FedresursResponseParser()

    def search(self, query: EntityQuery) -> SourceResult:
        try:
            response = self.transport.get(self.url_builder(query))
            return SourceResult(self.source_key, "found", response.url, self.parser.parse(response.text))
        except Exception as exc:
            return SourceResult(self.source_key, "error", error=str(exc))
