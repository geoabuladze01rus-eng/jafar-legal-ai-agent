from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .legal_entity_adapters import SourceResult
from .legal_entity_intelligence import EntityQuery
from .public_source_transport import SafePublicSourceTransport


@dataclass(frozen=True, slots=True)
class FnsResponseParser:
    """Conservative parser boundary for public FNS/EGRUL responses."""

    def parse(self, text: str) -> dict[str, Any]:
        # Parsing is intentionally schema-agnostic until a documented public
        # response contract is selected. Raw payload is never treated as fact.
        return {"raw_text": text}


class FnsPublicAdapter:
    source_key = "egrul"

    def __init__(
        self,
        transport: SafePublicSourceTransport,
        url_builder: Callable[[EntityQuery], str],
        parser: FnsResponseParser | None = None,
    ) -> None:
        self.transport = transport
        self.url_builder = url_builder
        self.parser = parser or FnsResponseParser()

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
            return SourceResult(
                source_key=self.source_key,
                status="error",
                error=str(exc),
            )
