from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260828165000_bind_action_approval_payload.sql"


def test_database_approval_payload_hash_is_immutable_and_required_for_execution() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "add column if not exists payload_hash text null" in sql
    assert "new.payload_hash is distinct from old.payload_hash" in sql
    assert "old.payload_hash is null" in sql
    assert "payload_binding_required" in sql
    assert "old.state = 'approved' and new.state = 'executed'" in sql


def test_execution_service_checks_payload_before_handler() -> None:
    source = (ROOT / "src" / "jafar" / "approval_execution.py").read_text(encoding="utf-8")

    mismatch = source.index("payload_mismatch")
    handler_lookup = source.index("handler = self._handlers.get")
    assert mismatch < handler_lookup
    assert "payload_fingerprint(payload)" in source
    assert "payload_binding_required" in source
