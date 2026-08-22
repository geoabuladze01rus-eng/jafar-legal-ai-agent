from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RiskFinding:
    code: str
    severity: str
    title: str
    details: str
    sources: tuple[str, ...]


class EntityRiskEngine:
    """Turns verified source findings into a conservative legal risk profile."""

    def evaluate(self, *, source_results: list[dict[str, Any]], verification_findings: list[dict[str, Any]] | None = None) -> list[RiskFinding]:
        findings: list[RiskFinding] = []
        for item in verification_findings or []:
            findings.append(RiskFinding("source_conflict", item.get("severity", "medium"), f"Расхождение по {item.get('field', 'полю')}", "Источники содержат разные сведения.", tuple(item.get("sources", []))))
        for item in source_results:
            data = item.get("result") or item.get("data") or {}
            source = str(item.get("source") or item.get("source_key") or "unknown")
            if item.get("status") in {"error", "unavailable"}:
                findings.append(RiskFinding("source_unavailable", "low", "Источник недоступен", f"Источник {source} не дал проверяемого результата.", (source,)))
            for flag in data.get("risk_flags", []) if isinstance(data, dict) else []:
                findings.append(RiskFinding("source_flag", "medium", str(flag), "Признак риска получен из источника.", (source,)))
        return findings

    @staticmethod
    def summary(findings: list[RiskFinding]) -> dict[str, Any]:
        order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        highest = max((f.severity for f in findings), key=lambda s: order.get(s, 0), default="none")
        return {"highest_severity": highest, "finding_count": len(findings), "findings": [f.__dict__ for f in findings]}
