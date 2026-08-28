from pathlib import Path


def test_reconciliation_audit_migration_is_server_only_and_append_only() -> None:
    sql = Path(
        "supabase/migrations/20260828213000_add_reconciliation_audit_ledger.sql"
    ).read_text(encoding="utf-8")
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.action_reconciliation_audit" in normalized
    assert "revoke all on table public.action_reconciliation_audit from public, anon, authenticated" in normalized
    assert "grant select, insert on table public.action_reconciliation_audit to service_role" in normalized
    assert "grant usage, select on sequence public.action_reconciliation_audit_id_seq to service_role" in normalized
    assert "before update on public.action_reconciliation_audit" in normalized
    assert "before delete on public.action_reconciliation_audit" in normalized
    assert "action_reconciliation_audit_is_append_only" in normalized
    assert "confirmed_not_executed" in normalized
    assert "confirmed_executed" in normalized


def test_reconciliation_rpc_updates_action_and_audit_in_one_transaction() -> None:
    sql = Path(
        "supabase/migrations/20260828214000_add_atomic_action_reconciliation_rpc.sql"
    ).read_text(encoding="utf-8")
    normalized = " ".join(sql.lower().split())

    assert "create or replace function public.reconcile_action_for_owner" in normalized
    assert "security definer" in normalized
    assert "for update" in normalized
    assert "state = 'approved'" in normalized
    assert "state = 'executed'" in normalized
    assert "insert into public.action_reconciliation_audit" in normalized
    assert "revoke all on function public.reconcile_action_for_owner(uuid, text, text, text, text) from public, anon, authenticated" in normalized
    assert "grant execute on function public.reconcile_action_for_owner(uuid, text, text, text, text) to service_role" in normalized
