from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from jafar.cost_scale_control import (
    BudgetLimits,
    CostLedger,
    CostRecord,
    CostScaleControl,
    TokenUsage,
    UsageContext,
)
from jafar.supabase_cost_reservations import SupabaseCostReservationRepository


class _Response:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self


class _RpcClient:
    def __init__(self):
        self.calls = []

    def rpc(self, function_name, params):
        self.calls.append((function_name, params))
        return _Response({"ok": True})


def _context(request_id: str, matter_id: str | None = "matter-1") -> UsageContext:
    return UsageContext(
        request_id=request_id,
        user_id="user-1",
        operation="legal_analysis",
        matter_id=matter_id,
    )


def _record(request_id: str, cost: str, matter_id: str = "matter-1") -> CostRecord:
    return CostRecord(
        context=_context(request_id, matter_id),
        provider="openai",
        model="model-a",
        usage=TokenUsage(input_tokens=100),
        cost_usd=Decimal(cost),
        recorded_at=datetime.now(UTC),
    )


def test_preflight_enforces_matter_daily_and_monthly_budgets() -> None:
    ledger = CostLedger()
    ledger.record(_record("existing", "0.80"))
    control = CostScaleControl(
        pricing={},
        ledger=ledger,
        limits=BudgetLimits(
            per_matter_daily_usd=Decimal("1.00"),
            per_matter_monthly_usd=Decimal("1.10"),
        ),
    )

    with pytest.raises(RuntimeError, match="matter_daily"):
        control.preflight(_context("daily"), estimated_cost_usd=Decimal("0.30"))

    monthly_only = CostScaleControl(
        pricing={},
        ledger=ledger,
        limits=BudgetLimits(per_matter_monthly_usd=Decimal("1.00")),
    )
    with pytest.raises(RuntimeError, match="matter_monthly"):
        monthly_only.preflight(
            _context("monthly"),
            estimated_cost_usd=Decimal("0.30"),
        )


def test_preflight_does_not_apply_matter_budget_without_matter_identity() -> None:
    control = CostScaleControl(
        pricing={},
        limits=BudgetLimits(per_matter_daily_usd=Decimal("0.01")),
    )

    control.preflight(
        _context("non-matter", matter_id=None),
        estimated_cost_usd=Decimal(100),
    )


def test_supabase_reservation_receives_matter_ceiling_parameters() -> None:
    client = _RpcClient()
    repository = SupabaseCostReservationRepository(client, "owner-1")

    repository.reserve(
        context=_context("reserve-1"),
        estimated_cost_usd=Decimal("0.50"),
        limits=BudgetLimits(
            per_user_daily_usd=Decimal(5),
            per_user_monthly_usd=Decimal(100),
            per_matter_daily_usd=Decimal(10),
            per_matter_monthly_usd=Decimal(200),
            global_daily_usd=Decimal(500),
        ),
    )

    function_name, params = client.calls[0]
    assert function_name == "reserve_ai_cost_for_owner"
    assert params["p_matter_id"] == "matter-1"
    assert params["p_matter_daily_limit_usd"] == "10"
    assert params["p_matter_monthly_limit_usd"] == "200"


def test_matter_budget_migration_is_service_role_only_and_atomic() -> None:
    migration = Path(
        "supabase/migrations/20260829041000_add_per_matter_ai_budgets.sql"
    ).read_text()

    assert "ai_spend_for_matter_for_owner" in migration
    assert "pg_advisory_xact_lock" in migration
    assert "cost_budget_exceeded:matter_daily" in migration
    assert "cost_budget_exceeded:matter_monthly" in migration
    assert "from public, anon, authenticated" in migration
    assert "to service_role" in migration
