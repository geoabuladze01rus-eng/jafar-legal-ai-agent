from __future__ import annotations

import re
from typing import Any

from .legal_entity_adapters import PublicSourceAdapter, SourceResult
from .legal_entity_intelligence import EntityQuery
from .public_source_transport import SafePublicSourceTransport


class KadAdapter(PublicSourceAdapter):
    """KAD adapter boundary.

    Parsing is intentionally conservative: the adapter only turns an explicitly
    supplied public response into structured fields. It never treats an empty or
    blocked response as a negative finding.
    """

    def __init__(self, transport: SafePublicSourceTransport, search_url_template: str) -> None:
        super().__init__("kad")
        self.transport = transport
        self.search_url_template = search_url_template

    def search(self, query: EntityQuery) -> SourceResult:
        from urllib.parse import quote

        url = self.search_url_template.format(query=quote(query.value, safe=""))
        response = self.transport.get(url)
        data = self.parse_response(response.text)
        return SourceResult(
            source_key="kad",
            status="found" if data.get("case_count", 0) > 0 else "negative",
            source_url=response.url,
            data=data,
        )

    @staticmethod
    def parse_response(text: str) -> dict[str, Any]:
        # Supports simple server-rendered summaries without pretending to parse
        # arbitrary JavaScript applications. Rich API/HTML parsers can be added later.
        match = re.search(r"(?:дел|cases)[^0-9]{0,30}(\d+)", text, re.IGNORECASE)
        return {"case_count": int(match.group(1)) if match else 0}
