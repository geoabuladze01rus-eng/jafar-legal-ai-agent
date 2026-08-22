from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..source_collector import SourceQuery, SourceResult


class FnsTransport(Protocol):
    def lookup(self, query: SourceQuery) -> dict[str, Any] | None: ...


@dataclass(slots=True)
class FnsEgrulAdapter:
    """Adapter boundary for official FNS EGRUL/EGRIP data.

    Transport is injected deliberately: the collector must not embed credentials,
    scraping rules, or undocumented endpoints. Official FNS integration can be
    enabled separately when access credentials are available.
    """

    transport: FnsTransport
    name: str = "fns_egrul"

    def collect(self, query: SourceQuery) -> SourceResult:
        if not any((query.name, query.inn, query.ogrn, query.kpp)):
            return SourceResult(self.name, "error", {}, "empty query")
        try:
            data = self.transport.lookup(query)
            if data is None:
                return SourceResult(self.name, "no_data", {})
            return SourceResult(self.name, "found", data)
        except TimeoutError as exc:
            return SourceResult(self.name, "timeout", {}, str(exc))
        except Exception as exc:
            return SourceResult(self.name, "error", {}, str(exc))
