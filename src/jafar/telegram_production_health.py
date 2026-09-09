from __future__ import annotations

from pydantic import BaseModel, Field


class TelegramProductionHealthSnapshot(BaseModel):
    """Read-only inputs from the Supabase production control plane."""

    cloud_publisher_enabled: bool
    cloud_publisher_dry_run: bool
    notion_sync_enabled: bool
    notion_sync_dry_run: bool
    telegram_token_present: bool
    publisher_cron_active: bool
    notion_sync_cron_active: bool
    last_publisher_cron_status: str | None = None
    last_sync_cron_status: str | None = None
    publisher_cron_fresh: bool = False
    notion_sync_cron_fresh: bool = False
    due_ready_count: int = Field(default=0, ge=0)
    claimed_count: int = Field(default=0, ge=0)
    stale_claimed_count: int = Field(default=0, ge=0)
    uncertain_count: int = Field(default=0, ge=0)
    reconciliation_required_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    make_v2_expected_inactive: bool


class TelegramProductionHealthReport(BaseModel):
    healthy: bool
    blockers: list[str]
    warnings: list[str]


def evaluate_production_health(
    snapshot: TelegramProductionHealthSnapshot,
) -> TelegramProductionHealthReport:
    """Evaluate the deployed Supabase topology without performing any mutation.

    Make v2 being active is a hard duplicate-delivery risk. Claimed, uncertain and
    reconciliation records are never treated as automatically retryable.
    """

    blockers: list[str] = []
    warnings: list[str] = []

    required_true = {
        "cloud_publisher_disabled": snapshot.cloud_publisher_enabled,
        "notion_sync_disabled": snapshot.notion_sync_enabled,
        "telegram_token_missing": snapshot.telegram_token_present,
        "publisher_cron_inactive": snapshot.publisher_cron_active,
        "notion_sync_cron_inactive": snapshot.notion_sync_cron_active,
        "publisher_cron_stale": snapshot.publisher_cron_fresh,
        "notion_sync_cron_stale": snapshot.notion_sync_cron_fresh,
        "make_v2_duplicate_delivery_risk": snapshot.make_v2_expected_inactive,
    }
    blockers.extend(reason for reason, condition in required_true.items() if not condition)

    if snapshot.cloud_publisher_dry_run:
        blockers.append("cloud_publisher_dry_run_enabled")
    if snapshot.notion_sync_dry_run:
        blockers.append("notion_sync_dry_run_enabled")
    if snapshot.last_publisher_cron_status != "succeeded":
        blockers.append("publisher_last_cron_not_succeeded")
    if snapshot.last_sync_cron_status != "succeeded":
        blockers.append("notion_sync_last_cron_not_succeeded")
    if snapshot.stale_claimed_count:
        blockers.append("stale_claims_require_reconciliation")
    if snapshot.uncertain_count:
        blockers.append("uncertain_delivery_requires_reconciliation")
    if snapshot.reconciliation_required_count:
        blockers.append("manual_reconciliation_required")

    if snapshot.failed_count:
        warnings.append("failed_delivery_records_present")
    if snapshot.claimed_count:
        warnings.append("publications_currently_claimed")
    if snapshot.due_ready_count:
        warnings.append("due_ready_publications_present")

    return TelegramProductionHealthReport(
        healthy=not blockers,
        blockers=blockers,
        warnings=warnings,
    )
