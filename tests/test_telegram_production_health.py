from __future__ import annotations

from jafar.telegram_production_health import (
    TelegramProductionHealthSnapshot,
    evaluate_production_health,
)


def _healthy_snapshot(**overrides):
    data = {
        "notion_connection_ok": True,
        "telegram_connection_ok": True,
        "scheduler_enabled": True,
    }
    data.update(overrides)
    return TelegramProductionHealthSnapshot(**data)


def test_clean_snapshot_is_healthy() -> None:
    report = evaluate_production_health(_healthy_snapshot())

    assert report.healthy is True
    assert report.blockers == []
    assert report.warnings == []


def test_uncertain_delivery_is_hard_blocker() -> None:
    report = evaluate_production_health(_healthy_snapshot(uncertain_delivery_count=1))

    assert report.healthy is False
    assert "uncertain_delivery_requires_reconciliation" in report.blockers


def test_stale_claim_and_reconciliation_block_production() -> None:
    report = evaluate_production_health(
        _healthy_snapshot(stale_claim_count=2, reconciliation_required_count=1)
    )

    assert report.healthy is False
    assert "stale_claims_require_reconciliation" in report.blockers
    assert "manual_reconciliation_required" in report.blockers


def test_failed_delivery_is_warning_not_automatic_retry() -> None:
    report = evaluate_production_health(_healthy_snapshot(failed_delivery_count=3))

    assert report.healthy is True
    assert report.warnings == ["failed_delivery_records_present"]


def test_disabled_scheduler_can_be_allowed_during_preflight() -> None:
    snapshot = _healthy_snapshot(scheduler_enabled=False, ready_due_count=2)

    production = evaluate_production_health(snapshot)
    preflight = evaluate_production_health(snapshot, require_scheduler_enabled=False)

    assert production.healthy is False
    assert "scheduler_disabled" in production.blockers
    assert preflight.healthy is True
    assert "due_publications_waiting_while_scheduler_disabled" in preflight.warnings
