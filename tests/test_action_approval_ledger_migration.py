from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260828164000_harden_action_approval_ledger.sql"


def test_approval_ledger_is_not_directly_mutable_by_clients() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").casefold()

    assert "revoke all on table public.action_approvals from anon, authenticated" in sql
    assert 'drop policy if exists "action approvals owner can insert"' in sql
    assert 'drop policy if exists "action approvals owner can update"' in sql


def test_approval_ledger_enforces_immutable_payload_and_forward_transitions() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").casefold()

    assert "immutable_action_approval_fields" in sql
    assert "old.state = 'proposed' and new.state in ('approved', 'rejected')" in sql
    assert "old.state = 'approved' and new.state = 'executed'" in sql
    assert "invalid_action_approval_transition" in sql
    assert "before update on public.action_approvals" in sql
