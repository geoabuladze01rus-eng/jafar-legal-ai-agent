from __future__ import annotations

from pydantic import BaseModel, Field


class TelegramProductionHealthSnapshot(BaseModel):
    notion_connection_ok: bool
    telegram_connection_ok: bool
    scheduler_enabled: bool
    ready_due_count: int = Field(default=0, ge=0)
    in_progress_count: int = Field(default=0, ge=0)
    stale_claim_count: int = Field(default=0, ge=0)
    uncertain_delivery_count: int = Field(default=0, ge=0)
    failed_delivery_count: int = Field(default=0, ge=0)
    reconciliation_required_count: int = Field(default=0, ge=0)


class TelegramProductionHealthReport(BaseModel):
    healthy: bool
    blockers: list[str]
    warnings: list[str]


def evaluate_production_health(
    snapshot: TelegramProductionHealthSnapshot,
    *,
    require_scheduler_enabled: bool = True,
) -> TelegramProductionHealthReport:
    """Evaluate operational readiness without treating unknown delivery as retryable.

    UNCERTAIN/reconciliation states are hard blockers because automatically retrying them
    can duplicate a message already accepted by Telegram.
    """

    blockers: list[str] = []
    warnings: list[str] = []

    if not snapshot.notion_connection_ok:
        blockers.append("notion_connection_unavailable")
    if not snapshot.telegram_connection_ok:
        blockers.append("telegram_connection_unavailable")
    if require_scheduler_enabled and not snapshot.scheduler_enabled:
        blockers.append("scheduler_disabled")
    if snapshot.stale_claim_count:
        blockers.append("stale_claims_require_reconciliation")
    if snapshot.uncertain_delivery_count:
        blockers.append("uncertain_delivery_requires_reconciliation")
    if snapshot.reconciliation_required_count:
        blockers.append("manual_reconciliation_required")

    if snapshot.failed_delivery_count:
        warnings.append("failed_delivery_records_present")
    if snapshot.ready_due_count and not snapshot.scheduler_enabled:
        warnings.append("due_publications_waiting_while_scheduler_disabled")
    if snapshot.in_progress_count:
        warnings.append("publications_currently_claimed")

    return TelegramProductionHealthReport(
        healthy=not blockers,
        blockers=blockers,
        warnings=warnings,
    )
