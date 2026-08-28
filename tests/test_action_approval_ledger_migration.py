from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARDEN = ROOT / "supabase" / "migrations" / "20260828164000_harden_action_approval_ledger.sql"
CLAIM = ROOT / "supabase" / "migrations" / "20260828210000_add_atomic_action_execution_claim.sql"


def test_approval_ledger_is_not_directly_mutable_by_clients() -> None:
    sql = HARDEN.read_text(encoding="utf-8").casefold()
    assert "revoke all on table public.action_approvals from anon, authenticated" in sql
    assert 'drop policy if exists "action approvals owner can insert"' in sql
    assert 'drop policy if exists "action approvals owner can update"' in sql


def test_latest_approval_lifecycle_requires_atomic_execution_claim() -> None:
    sql = CLAIM.read_text(encoding="utf-8").casefold()
    assert "'executing'" in sql
    assert "execution_claimed_at" in sql
    assert "execution_claimed_by" in sql
    assert "execution_error" in sql
    assert "old.state = 'approved' and new.state = 'executing'" in sql
    assert "old.state = 'executing' and new.state = 'approved'" in sql
    assert "old.state = 'executing' and new.state = 'executed'" in sql
    assert "execution_claim_required" in sql
    assert "execution_error_required_for_retry" in sql
    assert "immutable_action_approval_fields" in sql
    assert "new.payload_hash is distinct from old.payload_hash" in sql
    assert "invalid_action_approval_transition" in sql


def test_executed_state_keeps_claim_identity_for_audit() -> None:
    sql = CLAIM.read_text(encoding="utf-8").casefold()
    assert "state = 'executed'" in sql
    assert "execution_claimed_at is not null" in sql
    assert "execution_claimed_by is not null" in sql
    assert "executed_at is not null" in sql
