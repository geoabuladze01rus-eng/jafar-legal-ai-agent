from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from .legal_entity_adapters import PublicSourceAdapter, SourceResult
from .legal_entity_intelligence import EntityQuery
from .public_source_transport import SafePublicSourceTransport


class KadAdapter(PublicSourceAdapter):
    """KAD adapter boundary with conservative result semantics."""

    def __init__(self, transport: SafePublicSourceTransport, search_url_template: str) -> None:
        super().__init__("kad")
        self.transport = transport
        self.search_url_template = search_url_template

    def search(self, query: EntityQuery) -> SourceResult:
        url = self.search_url_template.format(query=quote(query.value, safe=""))
        try:
            response = self.transport.get(url)
            data = self.parse_response(response.text)
            status = "found" if data.get("case_count") is not None else "no_data"
            return SourceResult(source_key="kad", status=status, source_url=response.url, data=data)
        except TimeoutError as exc:
            return SourceResult(source_key="kad", status="timeout", error=str(exc))
        except Exception as exc:  # noqa: BLE001
            return SourceResult(source_key="kad", status="error", error=str(exc))

    @staticmethod
    def parse_response(text: str) -> dict[str, Any]:
        match = re.search(r"(?:дел|cases)[^0-9]{0,30}(\d+)", text, re.IGNORECASE)
        if not match:
            return {"case_count": None, "raw_available": bool(text.strip())}
        return {"case_count": int(match.group(1))}
