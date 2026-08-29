from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..source_collector import SourceQuery, SourceResult


@dataclass(slots=True)
class FsspAdapter:
    """FSSP public-source adapter boundary; transport is injected for testability."""

    transport: Callable[[SourceQuery], dict[str, Any]]
    name: str = "fssp"

    def collect(self, query: SourceQuery) -> SourceResult:
        if not any((query.name, query.inn, query.ogrn)):
            return SourceResult(self.name, "no_data", {})
        try:
            data = self.transport(query)
            status = "found" if data.get("records") else "negative"
            return SourceResult(self.name, status, data)
        except TimeoutError as exc:
            return SourceResult(self.name, "timeout", {}, str(exc))
        except Exception as exc:  # noqa: BLE001
            return SourceResult(self.name, "error", {}, str(exc))
