from pathlib import Path


def test_reconciliation_audit_migration_is_server_only_and_append_only() -> None:
    sql = Path(
        "supabase/migrations/20260828213000_add_reconciliation_audit_ledger.sql"
    ).read_text(encoding="utf-8")
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.action_reconciliation_audit" in normalized
    assert "revoke all on table public.action_reconciliation_audit from public, anon, authenticated" in normalized
    assert "grant select, insert on table public.action_reconciliation_audit to service_role" in normalized
    assert "before update on public.action_reconciliation_audit" in normalized
    assert "before delete on public.action_reconciliation_audit" in normalized
    assert "action_reconciliation_audit_is_append_only" in normalized
    assert "confirmed_not_executed" in normalized
    assert "confirmed_executed" in normalized
