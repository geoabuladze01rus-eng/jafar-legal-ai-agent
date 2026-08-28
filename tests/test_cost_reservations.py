from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from jafar.cost_scale_control import BudgetLimits, UsageContext
from jafar.supabase_cost_reservations import SupabaseCostReservationRepository


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260828173000_add_ai_cost_reservations.sql"


class FakeRPC:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return SimpleNamespace(data=self.data)


class FakeSupabase:
    def __init__(self) -> None:
        self.calls = []

    def rpc(self, function_name, params):
        self.calls.append((function_name, params))
        return FakeRPC({"ok": True} if function_name == "reserve_ai_cost_for_owner" else True)


def test_migration_uses_advisory_lock_and_service_role_only() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "pg_advisory_xact_lock" in sql
    assert "state in ('active', 'released', 'settled', 'expired')" in sql
    assert "auth.role() <> 'service_role'" in sql
    assert "cost_budget_exceeded:user_daily" in sql
    assert "cost_budget_exceeded:user_monthly" in sql
    assert "cost_budget_exceeded:global_daily" in sql
    assert "revoke all on public.ai_cost_reservations from anon, authenticated" in sql


def test_repository_reserves_with_server_side_limits_and_can_settle() -> None:
    client = FakeSupabase()
    repo = SupabaseCostReservationRepository(client, "owner-1")
    context = UsageContext("request-1", "user-1", "deep-analysis", "matter-1")
    limits = BudgetLimits(
        per_user_daily_usd=Decimal("5"),
        per_user_monthly_usd=Decimal("50"),
        global_daily_usd=Decimal("100"),
    )

    reservation = repo.reserve(
        context=context,
        estimated_cost_usd=Decimal("0.75"),
        limits=limits,
        ttl_seconds=60,
    )
    repo.settle(reservation.reservation_id)

    reserve_name, params = client.calls[0]
    assert reserve_name == "reserve_ai_cost_for_owner"
    assert params["p_reservation_id"] == "request-1"
    assert params["p_user_id"] == "user-1"
    assert params["p_matter_id"] == "matter-1"
    assert params["p_estimated_cost_usd"] == "0.75"
    assert params["p_user_daily_limit_usd"] == "5"
    assert client.calls[1][0] == "close_ai_cost_reservation_for_owner"
    assert client.calls[1][1]["p_state"] == "settled"
