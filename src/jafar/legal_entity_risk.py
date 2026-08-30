from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass(frozen=True, slots=True)
class RiskSignal:
    source: str
    code: str
    title: str
    severity: str
    confidence: float
    evidence: tuple[str, ...] = ()
    details: dict[str, Any] | None = None


class LegalEntityRiskEngine:
    """Aggregates source signals without turning missing data into negative findings."""

    WEIGHTS: ClassVar[dict[str, int]] = {"low": 1, "medium": 2, "high": 4, "critical": 8}

    def assess(self, signals: list[RiskSignal]) -> dict[str, Any]:
        score = sum(self.WEIGHTS.get(signal.severity, 0) * max(0.0, min(1.0, signal.confidence)) for signal in signals)
        if score >= 8:
            level = "critical"
        elif score >= 4:
            level = "high"
        elif score >= 2:
            level = "medium"
        else:
            level = "low"
        return {
            "risk_level": level,
            "score": round(score, 4),
            "signals": [self._serialize(signal) for signal in signals],
            "requires_human_review": bool(signals),
        }

    @staticmethod
    def _serialize(signal: RiskSignal) -> dict[str, Any]:
        return {
            "source": signal.source,
            "code": signal.code,
            "title": signal.title,
            "severity": signal.severity,
            "confidence": signal.confidence,
            "evidence": list(signal.evidence),
            "details": signal.details or {},
        }
