from datetime import UTC, datetime
from decimal import Decimal

from jafar.cost_dashboard import CostDashboardService, SpendScope
from jafar.cost_scale_control import BudgetLimits, CostRecord, TokenUsage, UsageContext


def record(request_id: str, cost: str, provider: str = "openai", model: str = "gpt", *, matter: str = "m1") -> CostRecord:
    return CostRecord(UsageContext(request_id, "lawyer-1", "analysis", matter), provider, model,
                      TokenUsage(input_tokens=1), Decimal(cost), recorded_at=datetime(2026, 8, 29, 10, tzinfo=UTC))


def test_cost_dashboard_derives_safe_threshold_events_and_breakdowns() -> None:
    snapshot = CostDashboardService().snapshot(
        records=(record("a", "0.50"), record("b", "0.25", "qwen", "qwen3")),
        limits=BudgetLimits(per_user_daily_usd=Decimal(1), per_matter_daily_usd=Decimal(1),
                            per_matter_monthly_usd=Decimal(1), global_daily_usd=Decimal(1)),
        user_id="lawyer-1", matter_id="m1", reserved_spend_usd=Decimal("0.10"),
        generated_at=datetime(2026, 8, 29, 12, tzinfo=UTC),
    )
    assert snapshot.today_spend_usd == Decimal("0.75")
    assert snapshot.month_spend_usd == Decimal("0.75")
    assert snapshot.reserved_spend_usd == Decimal("0.10")
    assert snapshot.budget_remaining_usd == Decimal("0.25")
    assert snapshot.percentage_used == Decimal("75.00")
    assert [(item.provider, item.settled_usd) for item in snapshot.provider_breakdown] == [("openai", Decimal("0.50")), ("qwen", Decimal("0.25"))]
    assert all(not hasattr(item, "prompt") for item in snapshot.alerts)
    assert {(item.scope, item.threshold_percent) for item in snapshot.alerts} >= {
        (SpendScope.USER_DAILY, 50), (SpendScope.USER_DAILY, 75),
        (SpendScope.MATTER_DAILY, 50), (SpendScope.MATTER_MONTHLY, 75),
        (SpendScope.GLOBAL_DAILY, 75),
    }


def test_cost_dashboard_does_not_emit_events_for_unconfigured_budget() -> None:
    snapshot = CostDashboardService().snapshot(
        records=(record("a", "3"),), limits=BudgetLimits(), user_id="lawyer-1",
        generated_at=datetime(2026, 8, 29, 12, tzinfo=UTC),
    )
    assert snapshot.alerts == ()
    assert snapshot.budget_remaining_usd is None
