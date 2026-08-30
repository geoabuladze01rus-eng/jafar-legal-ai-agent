"""Read-only, privacy-safe AI spend dashboard projections.

The projection deliberately contains no prompts, document content, client names, or legal
conclusions.  It is a dashboard signal for an attorney, never an execution trigger.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from .cost_scale_control import BudgetLimits, CostRecord


class SpendScope(StrEnum):
    USER_DAILY = "user_daily"
    MATTER_DAILY = "matter_daily"
    MATTER_MONTHLY = "matter_monthly"
    GLOBAL_DAILY = "global_daily"


@dataclass(frozen=True, slots=True)
class SpendAlert:
    """A derived internal dashboard event with opaque scope identifiers only."""

    scope: SpendScope
    threshold_percent: int
    percent_used: Decimal
    matter_id: str | None = None


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    provider: str
    model: str
    settled_usd: Decimal


@dataclass(frozen=True, slots=True)
class CostDashboardSnapshot:
    generated_at: datetime
    today_spend_usd: Decimal
    month_spend_usd: Decimal
    matter_today_spend_usd: Decimal | None
    matter_month_spend_usd: Decimal | None
    reserved_spend_usd: Decimal
    settled_spend_usd: Decimal
    budget_remaining_usd: Decimal | None
    percentage_used: Decimal | None
    provider_breakdown: tuple[CostBreakdown, ...]
    model_breakdown: tuple[CostBreakdown, ...]
    alerts: tuple[SpendAlert, ...]


class CostDashboardService:
    """Build a deterministic dashboard projection from already-metered records."""

    THRESHOLDS = (50, 75, 90, 100)

    def snapshot(
        self,
        *,
        records: Iterable[CostRecord],
        limits: BudgetLimits,
        user_id: str,
        matter_id: str | None = None,
        reserved_spend_usd: Decimal = Decimal(0),
        generated_at: datetime | None = None,
    ) -> CostDashboardSnapshot:
        if generated_at is None:
            generated_at = datetime.now(UTC)
        if generated_at.tzinfo is None:
            raise ValueError("generated_at_must_be_timezone_aware")
        if reserved_spend_usd < 0:
            raise ValueError("reserved_spend_must_be_non_negative")

        day_start = generated_at.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = day_start.replace(day=1)
        normalized_matter = matter_id.strip() if matter_id else None
        all_records = tuple(records)
        user_today = self._sum(all_records, since=day_start, user_id=user_id)
        user_month = self._sum(all_records, since=month_start, user_id=user_id)
        matter_today = (
            self._sum(all_records, since=day_start, matter_id=normalized_matter)
            if normalized_matter else None
        )
        matter_month = (
            self._sum(all_records, since=month_start, matter_id=normalized_matter)
            if normalized_matter else None
        )
        global_today = self._sum(all_records, since=day_start)
        settled = sum((item.cost_usd for item in all_records), Decimal(0))
        alerts = self._alerts(
            user_today=user_today,
            matter_today=matter_today,
            matter_month=matter_month,
            global_today=global_today,
            limits=limits,
            matter_id=normalized_matter,
        )
        selected_spend, selected_limit = self._selected_budget(
            matter_today=matter_today,
            matter_month=matter_month,
            user_today=user_today,
            limits=limits,
        )
        return CostDashboardSnapshot(
            generated_at=generated_at,
            today_spend_usd=user_today,
            month_spend_usd=user_month,
            matter_today_spend_usd=matter_today,
            matter_month_spend_usd=matter_month,
            reserved_spend_usd=reserved_spend_usd,
            settled_spend_usd=settled,
            budget_remaining_usd=(max(Decimal(0), selected_limit - selected_spend)
                                  if selected_limit is not None else None),
            percentage_used=((selected_spend / selected_limit * 100).quantize(Decimal("0.01"))
                             if selected_limit is not None else None),
            provider_breakdown=self._breakdown(all_records, by_model=False),
            model_breakdown=self._breakdown(all_records, by_model=True),
            alerts=alerts,
        )

    @staticmethod
    def _sum(records: Iterable[CostRecord], *, since: datetime, user_id: str | None = None,
             matter_id: str | None = None) -> Decimal:
        return sum((record.cost_usd for record in records if record.recorded_at >= since
                    and (user_id is None or record.context.user_id == user_id)
                    and (matter_id is None or record.context.matter_id == matter_id)), Decimal(0))

    def _alerts(self, *, user_today: Decimal, matter_today: Decimal | None,
                matter_month: Decimal | None, global_today: Decimal, limits: BudgetLimits,
                matter_id: str | None) -> tuple[SpendAlert, ...]:
        candidates = ((SpendScope.USER_DAILY, user_today, limits.per_user_daily_usd, None),
                      (SpendScope.GLOBAL_DAILY, global_today, limits.global_daily_usd, None),
                      (SpendScope.MATTER_DAILY, matter_today, limits.per_matter_daily_usd, matter_id),
                      (SpendScope.MATTER_MONTHLY, matter_month, limits.per_matter_monthly_usd, matter_id))
        alerts: list[SpendAlert] = []
        for scope, spend, limit, scoped_matter_id in candidates:
            if spend is None or limit is None:
                continue
            percent = spend / limit * 100
            for threshold in self.THRESHOLDS:
                if percent >= threshold:
                    alerts.append(SpendAlert(scope, threshold, percent.quantize(Decimal("0.01")), scoped_matter_id))
        return tuple(alerts)

    @staticmethod
    def _selected_budget(*, matter_today: Decimal | None, matter_month: Decimal | None,
                         user_today: Decimal, limits: BudgetLimits) -> tuple[Decimal, Decimal | None]:
        if matter_month is not None and limits.per_matter_monthly_usd is not None:
            return matter_month, limits.per_matter_monthly_usd
        if matter_today is not None and limits.per_matter_daily_usd is not None:
            return matter_today, limits.per_matter_daily_usd
        return user_today, limits.per_user_daily_usd

    @staticmethod
    def _breakdown(records: Iterable[CostRecord], *, by_model: bool) -> tuple[CostBreakdown, ...]:
        totals: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal(0))
        for record in records:
            key = (record.provider, record.model if by_model else "")
            totals[key] += record.cost_usd
        return tuple(CostBreakdown(provider, model, cost) for (provider, model), cost in
                     sorted(totals.items(), key=lambda item: (-item[1], item[0])))
