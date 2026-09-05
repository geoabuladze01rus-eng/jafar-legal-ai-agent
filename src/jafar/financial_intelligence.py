from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Any


@dataclass(frozen=True, slots=True)
class FinancialPeriod:
    year: int
    revenue: float | None = None
    profit: float | None = None
    assets: float | None = None
    liabilities: float | None = None


class FinancialIntelligence:
    """Normalizes available financial statements and produces conservative risk signals."""

    def analyze(self, periods: list[FinancialPeriod]) -> dict[str, Any]:
        ordered = sorted(periods, key=lambda p: p.year)
        signals: list[dict[str, Any]] = []
        for previous, current in pairwise(ordered):
            if current.revenue is not None and previous.revenue not in (None, 0):
                change = (current.revenue - previous.revenue) / abs(previous.revenue)
                if change <= -0.30:
                    signals.append({"type": "revenue_decline", "year": current.year, "change": change, "severity": "high"})
            if current.profit is not None and current.profit < 0:
                signals.append({"type": "loss", "year": current.year, "severity": "medium"})
            if current.liabilities is not None and current.assets not in (None, 0):
                ratio = current.liabilities / current.assets
                if ratio >= 0.80:
                    signals.append({"type": "high_liability_ratio", "year": current.year, "ratio": ratio, "severity": "high"})
        return {"periods": [self._serialize(p) for p in ordered], "signals": signals}

    @staticmethod
    def _serialize(period: FinancialPeriod) -> dict[str, Any]:
        return {"year": period.year, "revenue": period.revenue, "profit": period.profit, "assets": period.assets, "liabilities": period.liabilities}
