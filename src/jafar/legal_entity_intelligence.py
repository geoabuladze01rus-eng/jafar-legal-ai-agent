from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class EntityQuery:
    name: str | None = None
    inn: str | None = None
    ogrn: str | None = None
    kpp: str | None = None

    def normalized(self) -> "EntityQuery":
        return EntityQuery(*(value.strip() if value else None for value in (self.name, self.inn, self.ogrn, self.kpp)))


@dataclass(frozen=True)
class SourceFinding:
    source_key: str
    status: str
    title: str
    details: dict[str, Any]
    source_url: str | None = None
    confidence: float = 0.0


class EntitySource(Protocol):
    source_key: str
    def lookup(self, query: EntityQuery) -> SourceFinding: ...


@dataclass(frozen=True)
class RiskFinding:
    code: str
    title: str
    severity: str
    rationale: str
    source_keys: tuple[str, ...]


@dataclass(frozen=True)
class InvestigationResult:
    query: EntityQuery
    profile: dict[str, Any]


class LegalEntityIntelligence:
    """Source-neutral public/free-source aggregator for Russian legal entities."""

    def __init__(self, sources: list[EntitySource] | None = None) -> None:
        self.sources = sources or []

    def investigate(self, query: EntityQuery) -> dict[str, Any]:
        q = query.normalized()
        if not any((q.name, q.inn, q.ogrn, q.kpp)):
            raise ValueError("At least one entity identifier is required")
        findings = []
        for source in self.sources:
            try:
                findings.append(source.lookup(q))
            except Exception as exc:
                findings.append(SourceFinding(source.source_key, "error", source.source_key, {}, error_to_details(exc)))
        return self.build_profile(findings)

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
            "risks": [asdict(r) for r in risks],
            "findings": [asdict(f) for f in findings],
            "disclaimer": "Отсутствие сведений в конкретном публичном источнике не доказывает отсутствие обстоятельства.",
        }

    def _score(self, findings: list[SourceFinding]) -> list[RiskFinding]:
        risks: list[RiskFinding] = []
        by_source = {f.source_key: f for f in findings}
        fedresurs = by_source.get("fedresurs")
        if fedresurs and fedresurs.status == "found" and fedresurs.details.get("bankruptcy"):
            risks.append(RiskFinding("bankruptcy", "Признаки банкротства", "critical", "Обнаружены сведения о банкротстве.", ("fedresurs",)))
        fssp = by_source.get("fssp")
        if fssp and fssp.status == "found":
            amount = fssp.details.get("debt_amount")
            if isinstance(amount, (int, float)) and amount > 0:
                risks.append(RiskFinding("enforcement_debt", "Исполнительные производства", "high" if amount >= 1_000_000 else "medium", f"Обнаружена задолженность: {amount}.", ("fssp",)))
        kad = by_source.get("kad")
        if kad and kad.status == "found":
            count = kad.details.get("case_count")
            if isinstance(count, int) and count > 0:
                risks.append(RiskFinding("arbitration_activity", "Арбитражная активность", "high" if count >= 20 else "medium", f"Найдено дел: {count}.", ("kad",)))
        finance = by_source.get("bo")
        if finance and finance.status == "found":
            loss = finance.details.get("net_loss")
            if isinstance(loss, (int, float)) and loss > 0:
                risks.append(RiskFinding("financial_loss", "Убыток по отчётности", "medium", f"Зафиксирован убыток: {loss}.", ("bo",)))
        return risks

    @staticmethod
    def _score_value(risks: list[RiskFinding]) -> int:
        return min(100, sum({"low": 10, "medium": 25, "high": 50, "critical": 80}[r.severity] for r in risks))

    @staticmethod
    def _risk_level(risks: list[RiskFinding]) -> str:
        if any(r.severity == "critical" for r in risks): return "critical"
        if any(r.severity == "high" for r in risks): return "high"
        if any(r.severity == "medium" for r in risks): return "medium"
        return "low" if risks else "unknown"

    def run(self, query: EntityQuery) -> InvestigationResult:
        normalized = query.normalized()
        return InvestigationResult(normalized, self.investigate(normalized))


def error_to_details(exc: Exception) -> dict[str, Any]:
    return {"reason": str(exc), "type": type(exc).__name__}
