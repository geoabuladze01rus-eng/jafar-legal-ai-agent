from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceFinding:
    source_key: str
    status: str  # found | negative | no_data | error
    title: str
    details: dict[str, Any]
    source_url: str | None = None


@dataclass(frozen=True)
class RiskFinding:
    code: str
    title: str
    severity: str  # low | medium | high | critical
    rationale: str
    source_keys: tuple[str, ...]


class LegalEntityIntelligence:
    """Normalizes public-source findings and calculates a transparent risk profile.

    Network access is intentionally outside this class. Adapters can be added per
    source without coupling source-specific HTML/API details to legal scoring.
    """

    def build_profile(self, findings: list[SourceFinding]) -> dict[str, Any]:
        risks = self._score(findings)
        return {
            "sources_checked": len(findings),
            "sources_found": sum(f.status == "found" for f in findings),
            "sources_negative": sum(f.status == "negative" for f in findings),
            "sources_no_data": sum(f.status == "no_data" for f in findings),
            "sources_error": sum(f.status == "error" for f in findings),
            "risk_score": self._score_value(risks),
            "risk_level": self._risk_level(risks),
            "risks": [r.__dict__ for r in risks],
            "findings": [f.__dict__ for f in findings],
            "disclaimer": "Отсутствие сведений в конкретном публичном источнике не доказывает отсутствие обстоятельства.",
        }

    def _score(self, findings: list[SourceFinding]) -> list[RiskFinding]:
        risks: list[RiskFinding] = []
        by_source = {f.source_key: f for f in findings}

        fedresurs = by_source.get("fedresurs")
        if fedresurs and fedresurs.status == "found" and fedresurs.details.get("bankruptcy"):
            risks.append(RiskFinding("bankruptcy", "Признаки банкротства", "critical", "В источнике обнаружены сведения о банкротстве.", ("fedresurs",)))

        fssp = by_source.get("fssp")
        if fssp and fssp.status == "found":
            amount = fssp.details.get("debt_amount")
            if isinstance(amount, (int, float)) and amount > 0:
                severity = "high" if amount >= 1_000_000 else "medium"
                risks.append(RiskFinding("enforcement_debt", "Исполнительные производства", severity, f"Обнаружена сумма задолженности: {amount}.", ("fssp",)))

        kad = by_source.get("kad")
        if kad and kad.status == "found":
            count = kad.details.get("case_count")
            if isinstance(count, int) and count > 0:
                severity = "high" if count >= 20 else "medium"
                risks.append(RiskFinding("arbitration_activity", "Арбитражная активность", severity, f"Найдено арбитражных дел: {count}.", ("kad",)))

        finance = by_source.get("bo")
        if finance and finance.status == "found":
            revenue = finance.details.get("revenue")
            loss = finance.details.get("net_loss")
            if isinstance(loss, (int, float)) and loss > 0:
                risks.append(RiskFinding("financial_loss", "Убыток по отчётности", "medium", f"Зафиксирован убыток: {loss}.", ("bo",)))
            if isinstance(revenue, (int, float)) and revenue == 0:
                risks.append(RiskFinding("zero_revenue", "Нулевая выручка", "low", "В предоставленной финансовой выборке выручка равна нулю.", ("bo",)))

        return risks

    @staticmethod
    def _score_value(risks: list[RiskFinding]) -> int:
        weights = {"low": 10, "medium": 25, "high": 50, "critical": 80}
        return min(100, sum(weights[r.severity] for r in risks))

    @staticmethod
    def _risk_level(risks: list[RiskFinding]) -> str:
        if any(r.severity == "critical" for r in risks):
            return "critical"
        if any(r.severity == "high" for r in risks):
            return "high"
        if any(r.severity == "medium" for r in risks):
            return "medium"
        if risks:
            return "low"
        return "unknown"
