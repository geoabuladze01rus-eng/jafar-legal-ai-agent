from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260923221000_harden_editorial_autopilot_review_gate.sql"
PUBLISHER = ROOT / "supabase/functions/telegram-publisher-v3/index.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_autopilot_cannot_self_certify_ready_publication() -> None:
    sql = _read(MIGRATION).lower()

    assert "before insert on public.telegram_publication_queue" in sql
    assert "like 'autopilot:%'" in sql
    assert "new.status := 'review'" in sql
    assert "new.fact_check_status := 'pending'" in sql
    assert "new.legal_risk := 'medium'" in sql
    assert "new.privacy_risk := 'medium'" in sql
    assert "autopilot_human_review_required" in sql
    assert "before update" not in sql


def test_autopilot_review_gate_is_non_destructive_and_service_role_scoped() -> None:
    sql = _read(MIGRATION).lower()

    assert "delete from" not in sql
    assert "truncate" not in sql
    assert "drop table" not in sql
    assert "revoke all on function public.enforce_editorial_autopilot_review_gate()" in sql
    assert "grant execute on function public.enforce_editorial_autopilot_review_gate()" in sql
    assert "to service_role" in sql


def test_publisher_still_requires_ready_and_clean_safety_fields() -> None:
    source = _read(PUBLISHER)

    assert "?status=eq.Ready&delivery_state=eq.pending&reconciliation_required=eq.false" in source
    assert 'row.status !== "Ready"' in source
    assert "fact_check_not_verified" in source
    assert 'row.legal_risk !== "low"' in source
    assert 'row.privacy_risk !== "low"' in source
    assert "editorial_blockers_present" in source


def test_autopilot_notion_bypass_does_not_bypass_queue_safety_gate() -> None:
    source = _read(PUBLISHER)

    validate_pos = source.index("const reasons = validate(row, visual)")
    notion_pos = source.index("reasons.push(...await revalidateNotion(row))")
    claim_pos = source.index('rpc<boolean>("claim_telegram_publication_queue_v3"')

    assert validate_pos < notion_pos < claim_pos
    assert 'source.startsWith("autopilot:")' in source
