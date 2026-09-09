from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "supabase/functions/telegram-publisher-v3/index.ts"
EGRESS = ROOT / "supabase/functions/telegram-egress/index.ts"
NOTION_SYNC = ROOT / "supabase/functions/telegram-notion-sync-v3/index.ts"
NOTION_GUARD = ROOT / "supabase/functions/telegram-notion-guard-v3/index.ts"
DELIVERY_MIGRATION = (
    ROOT / "supabase/migrations/20260908193000_add_telegram_publication_delivery.sql"
)
SYNC_MIGRATION = (
    ROOT / "supabase/migrations/20260909161000_telegram_notion_sync_v3_contract.sql"
)
HARDENING_MIGRATION = (
    ROOT / "supabase/migrations/20260909190000_harden_telegram_cloud_contract.sql"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_publisher_enforces_complete_ready_safety_gate() -> None:
    source = _read(PUBLISHER)

    for contract in (
        'row.status !== "Ready"',
        'row.fact_check_status',
        '["verified", "not_required"]',
        'row.legal_risk !== "low"',
        'row.privacy_risk !== "low"',
        "row.current_case_risk",
        "editorial_blockers_present",
        "content_fingerprint_invalid",
        "publish_time_not_due",
        "delivery_state_not_pending",
        "reconciliation_required",
        "already_has_telegram_message_id",
    ):
        assert contract in source


def test_final_notion_guard_runs_before_atomic_claim_and_detects_ready_to_review() -> None:
    publisher = _read(PUBLISHER)
    guard = _read(NOTION_GUARD)

    assert publisher.index("revalidateNotion(row)") < publisher.index(
        'rpc<boolean>("claim_telegram_publication_queue_v3"'
    )
    assert 'status !== "Ready"' in guard
    assert 'reasons.push("notion_status_not_ready")' in guard
    for field in (
        "Publication ID",
        "Publication Type",
        "Publish Date",
        "Content Fingerprint",
        "Delivery State",
        "Telegram Message ID",
        "Reconciliation Required",
        "Fact Check Status",
        "Legal Risk",
        "Privacy Risk",
        "Current Case Risk",
        "Editorial Blockers",
        "Content",
        "Caption",
        "Question",
        "Options JSON",
        "Correct Option IDs JSON",
        "Explanation",
        "Visual Asset Key",
        "Visual Category",
    ):
        assert f'p["{field}"]' in guard


def test_delivery_hash_covers_every_telegram_payload_field() -> None:
    source = _read(PUBLISHER)
    block = source[source.index("function stableHashInput") : source.index("async function sha256Hex")]

    for field in (
        "chat_id",
        "publication_type",
        "content",
        "caption",
        "visual_asset_key",
        "visual_category",
        "visual_sha256",
        "question",
        "options",
        "correct_option_ids",
        "explanation",
    ):
        assert field in block


def test_atomic_ledger_never_blindly_reclaims_terminal_or_ambiguous_state() -> None:
    sql = _read(DELIVERY_MIGRATION).lower()

    assert "where public.telegram_publication_delivery.state = 'pending'" in sql
    assert "public.telegram_publication_delivery.payload_hash = excluded.payload_hash" in sql
    assert "where publication_id = p_publication_id\n    and state = 'failed'" in sql
    assert "where publication_id = p_publication_id\n    and state = 'uncertain'" in sql
    assert "revoke all on function public.claim_telegram_publication" in sql
    assert "grant execute on function public.claim_telegram_publication(text, text) to service_role" in sql


def test_post_send_failures_are_uncertain_and_commit_ambiguity_is_reconciled() -> None:
    source = _read(PUBLISHER)

    assert "telegram_egress_transport_error" in source
    assert "telegram_egress_non_ok" in source
    assert "telegram_sent_but_database_commit_ambiguous" in source
    assert "telegram_sent_database_reconciliation_unavailable" in source
    assert 'outcome: "uncertain"' in source
    assert 'outcome: "sent_confirmed_after_commit_error"' in source
    assert "mark_telegram_publication_failed_v3" not in source


def test_notion_writeback_failure_cannot_trigger_a_resend() -> None:
    sync = _read(NOTION_SYNC)
    sql = _read(SYNC_MIGRATION)

    assert "telegram-egress" not in sync
    assert 'outcome: "writeback_error"' in sync
    assert "notion_sync_pending=true" in sql.replace(" ", "")
    assert "delivery_state <> 'pending'" in sql
    assert "return 'blocked_existing_state'" in sql


def test_egress_is_service_role_only_vault_only_and_not_a_generic_proxy() -> None:
    source = _read(EGRESS)
    config = _read(ROOT / "supabase/config.toml")

    assert "[functions.telegram-egress]\nverify_jwt = true" in config
    assert "internalAuthorized(req)" in source
    assert "`Bearer ${SERVICE_KEY}`" in source
    assert '"-1004412524447"' in source
    assert "ALLOWED_CHAT_IDS.has(chatId)" in source
    assert 'rpc<unknown>("get_telegram_bot_token_for_egress", {})' in source
    assert "x-telegram-bot-token" not in source
    assert 'new Set(["sendMessage", "sendPhoto", "sendPoll"])' in source
    assert '"probe"' not in source
    assert '"sendVideo"' not in source
    assert "telegram_message_id: telegramMessageId" in source
    assert "telegram: telegramBody" not in source


def test_photo_pipeline_requires_approved_versioned_asset_and_binary_payload() -> None:
    publisher = _read(PUBLISHER)
    migration = _read(
        ROOT / "supabase/migrations/20260909070000_add_telegram_visual_assets.sql"
    ).lower()

    assert "visual_asset_key_missing" in publisher
    assert "visual_category_missing" in publisher
    assert "visual_asset_unresolved" in publisher
    assert "photo_base64: visual.data_base64" in publisher
    assert "mime_type: visual.mime_type" in publisher
    assert "visual_base64_invalid" in publisher
    assert "visual_size_invalid" in publisher
    assert "v.approved is true" in migration
    assert "v.active is true" in migration
    assert "v.category = p_category" in migration


def test_poll_quiz_use_current_bot_api_contract_and_limits() -> None:
    publisher = _read(PUBLISHER)
    egress = _read(EGRESS)

    assert "options.length < 2 || options.length > 12" in publisher
    assert "question.length > 300" in publisher
    assert "x.length > 100" in publisher
    assert "invalid_correct_option_ids" in publisher
    assert "explanation_too_long" in publisher
    assert "explanation_too_many_line_feeds" in publisher
    assert "body.correct_option_id !==" not in egress
    assert "payload.correct_option_ids = correctIds" in egress
    assert "quiz_multiple_answers_not_supported" in egress


def test_notion_sync_is_ready_only_and_cannot_overwrite_delivery_authority() -> None:
    sync = _read(NOTION_SYNC)
    sql = _read(SYNC_MIGRATION)

    assert 'status: { equals: "Ready" }' in sync
    assert "fact_check_not_verified" in sync
    assert "legal_risk_not_low" in sync
    assert "privacy_risk_not_low" in sync
    assert "editorial_blockers_present" in sync
    for state in ("pending", "claimed", "sent", "failed", "uncertain"):
        assert state in _read(DELIVERY_MIGRATION)
    assert "v_existing.delivery_state <> 'pending'" in sql
    assert "v_existing.telegram_message_id is not null" in sql
    assert "raise exception 'fact_check_not_verified'" in sql
    assert "raise exception 'legal_risk_not_low'" in sql
    assert "raise exception 'privacy_risk_not_low'" in sql
    assert "raise exception 'current_case_risk'" in sql
    assert "raise exception 'editorial_blockers_present'" in sql


def test_cloud_schema_is_reproducible_and_secret_rpcs_are_service_role_only() -> None:
    sql = _read(SYNC_MIGRATION).lower()

    assert "create table if not exists public.telegram_publisher_config" in sql
    assert "create table if not exists public.telegram_publication_queue" in sql
    assert "enabled boolean not null default false" in sql
    assert "dry_run boolean not null default true" in sql
    assert "alter table public.telegram_publication_queue enable row level security" in sql
    assert "alter table public.telegram_publisher_config enable row level security" in sql
    for function in (
        "get_jafar_worker_secret_for_publisher()",
        "get_telegram_bot_token_for_egress()",
        "telegram_bot_token_present()",
    ):
        assert f"revoke all on function public.{function}" in sql
        assert f"grant execute on function public.{function} to service_role" in sql
    assert "jafar-telegram-publisher-v3" in sql
    assert "jafar-telegram-notion-sync-v3" in sql


def test_deployed_queue_hardening_is_non_destructive_and_fail_closed() -> None:
    sql = _read(HARDENING_MIGRATION).lower()

    assert "delete from" not in sql
    assert "truncate" not in sql
    assert "drop table" not in sql
    assert "before insert or update on public.telegram_publication_queue" in sql
    assert "telegram_publication_queue_touch_updated_at" in sql
    for gate in (
        "fact_check_not_verified",
        "legal_risk_not_low",
        "privacy_risk_not_low",
        "current_case_risk",
        "editorial_blockers_present",
        "content_fingerprint_invalid",
        "delivery_not_clean",
        "approved_visual_required",
        "options_invalid",
        "correct_option_ids_invalid",
    ):
        assert gate in sql
    assert "revoke all on function public.enforce_telegram_ready_queue_safety()" in sql


def test_retired_bot_access_returns_410_and_keeps_platform_jwt() -> None:
    retired = _read(ROOT / "supabase/functions/telegram-bot-access-v3/index.ts")
    config = _read(ROOT / "supabase/config.toml")

    assert "status: 410" in retired
    assert 'error: "retired"' in retired
    assert "[functions.telegram-bot-access-v3]\nverify_jwt = true" in config
