from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .legal_entity_adapters import SourceResult
from .legal_entity_intelligence import EntityQuery
from .public_source_transport import SafePublicSourceTransport


@dataclass(frozen=True, slots=True)
class FedresursResponseParser:
    def parse(self, text: str) -> dict[str, Any]:
        match = re.search(r"(?:сообщен|публик|messages)[^0-9]{0,40}(\d+)", text, re.IGNORECASE)
        return {
            "message_count": int(match.group(1)) if match else None,
            "raw_available": bool(text.strip()),
        }


class FedresursPublicAdapter:
    """Adapter for public Fedresurs messages; raw source remains auditable."""

    source_key = "fedresurs"

    def __init__(self, transport: SafePublicSourceTransport, url_builder: Callable[[EntityQuery], str], parser: FedresursResponseParser | None = None) -> None:
        self.transport = transport
        self.url_builder = url_builder
        self.parser = parser or FedresursResponseParser()

    def search(self, query: EntityQuery) -> SourceResult:
        url = self.url_builder(query)
        try:
            response = self.transport.get(url)
            data = self.parser.parse(response.text)
            status = "found" if data["message_count"] is not None else "no_data"
            return SourceResult(self.source_key, status, response.url, data)
        except TimeoutError as exc:
            return SourceResult(self.source_key, "timeout", error=str(exc))
        except Exception as exc:
            return SourceResult(self.source_key, "error", error=str(exc))
