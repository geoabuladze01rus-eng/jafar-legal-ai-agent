from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .legal_entity_adapters import SourceResult
from .legal_entity_intelligence import EntityQuery
from .public_source_transport import SafePublicSourceTransport


@dataclass(frozen=True, slots=True)
class FinancialResponseParser:
    def parse(self, text: str) -> dict[str, Any]:
        return {"raw_text": text}


class FinancialPublicAdapter:
    source_key = "bo"

    def __init__(self, transport: SafePublicSourceTransport, url_builder: Callable[[EntityQuery], str], parser: FinancialResponseParser | None = None) -> None:
        self.transport = transport
        self.url_builder = url_builder
        self.parser = parser or FinancialResponseParser()

    def search(self, query: EntityQuery) -> SourceResult:
        try:
            response = self.transport.get(self.url_builder(query))
            return SourceResult(self.source_key, "found", response.url, self.parser.parse(response.text))
        except Exception as exc:  # noqa: BLE001 - public source failures are isolated.
            return SourceResult(self.source_key, "error", error=str(exc))
