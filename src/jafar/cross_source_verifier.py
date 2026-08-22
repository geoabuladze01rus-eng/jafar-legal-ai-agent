from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .legal_entity_adapters import SourceResult


@dataclass(frozen=True, slots=True)
class VerificationFinding:
    field: str
    values: tuple[str, ...]
    sources: tuple[str, ...]
    severity: str


class CrossSourceVerifier:
    """Detects conflicting entity facts without choosing a value silently."""

    FIELDS = ("name", "inn", "ogrn", "status", "address")

    def verify(self, results: list[SourceResult]) -> list[VerificationFinding]:
        findings: list[VerificationFinding] = []
        for field in self.FIELDS:
            values: dict[str, list[str]] = defaultdict(list)
            for source in results:
                value = (source.data or {}).get(field)
                if value not in (None, ""):
                    values[str(value)].append(source.source_key)
            if len(values) > 1:
                findings.append(VerificationFinding(field, tuple(values.keys()), tuple(sorted({s for names in values.values() for s in names})), "high" if field in {"inn", "ogrn", "status"} else "medium"))
        return findings

    @staticmethod
    def to_risk_flags(findings: list[VerificationFinding]) -> list[dict[str, Any]]:
        return [{"type": "source_conflict", "field": f.field, "severity": f.severity, "values": list(f.values), "sources": list(f.sources)} for f in findings]
