from __future__ import annotations

from jafar.telegram_production_health import (
    TelegramProductionHealthSnapshot,
    evaluate_production_health,
)


def _healthy_snapshot(**overrides):
    data = {
        "cloud_publisher_enabled": True,
        "cloud_publisher_dry_run": False,
        "notion_sync_enabled": True,
        "notion_sync_dry_run": False,
        "telegram_token_present": True,
        "publisher_cron_active": True,
        "notion_sync_cron_active": True,
        "last_publisher_cron_status": "succeeded",
        "last_sync_cron_status": "succeeded",
        "publisher_cron_fresh": True,
        "notion_sync_cron_fresh": True,
        "make_v2_expected_inactive": True,
    }
    data.update(overrides)
    return TelegramProductionHealthSnapshot(**data)


def test_clean_supabase_snapshot_is_healthy() -> None:
    report = evaluate_production_health(_healthy_snapshot())

    assert report.healthy is True
    assert report.blockers == []
    assert report.warnings == []


def test_make_v2_active_is_duplicate_delivery_blocker() -> None:
    report = evaluate_production_health(_healthy_snapshot(make_v2_expected_inactive=False))

    assert report.healthy is False
    assert "make_v2_duplicate_delivery_risk" in report.blockers


def test_dry_run_or_stale_cron_blocks_live_readiness() -> None:
    report = evaluate_production_health(
        _healthy_snapshot(cloud_publisher_dry_run=True, notion_sync_cron_fresh=False)
    )

    assert report.healthy is False
    assert "cloud_publisher_dry_run_enabled" in report.blockers
    assert "notion_sync_cron_stale" in report.blockers


def test_uncertain_delivery_is_hard_blocker() -> None:
    report = evaluate_production_health(_healthy_snapshot(uncertain_count=1))

    assert report.healthy is False
    assert "uncertain_delivery_requires_reconciliation" in report.blockers


def test_stale_claim_and_reconciliation_block_production() -> None:
    report = evaluate_production_health(
        _healthy_snapshot(stale_claimed_count=2, reconciliation_required_count=1)
    )

    assert report.healthy is False
    assert "stale_claims_require_reconciliation" in report.blockers
    assert "manual_reconciliation_required" in report.blockers


def test_non_stale_claim_due_and_failed_rows_are_visible_warnings() -> None:
    report = evaluate_production_health(
        _healthy_snapshot(claimed_count=1, due_ready_count=2, failed_count=3)
    )

    assert report.healthy is True
    assert report.warnings == [
        "failed_delivery_records_present",
        "publications_currently_claimed",
        "due_ready_publications_present",
    ]
