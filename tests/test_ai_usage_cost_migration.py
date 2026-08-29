from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260828170000_add_ai_usage_cost_ledger.sql"


def test_ai_usage_cost_ledger_is_server_only_and_indexed() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create table if not exists public.ai_usage_costs" in sql
    assert "primary key (owner_user_id, request_id)" in sql
    assert "cached_input_tokens <= input_tokens" in sql
    assert "cost_usd >= 0" in sql
    assert "owner_user_id, user_id, recorded_at desc" in sql
    assert "revoke all on public.ai_usage_costs from anon, authenticated" in sql


def test_ai_spend_rpc_is_service_role_only() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.ai_spend_for_owner" in sql
    assert "security definer" in sql
    assert "p_user_id is null or user_id = p_user_id" in sql
    assert "from authenticated" in sql
    assert "to service_role" in sql
