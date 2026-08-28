from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from enum import StrEnum

from pydantic import BaseModel, Field

from .matter_repository import MatterRepository


class DashboardSignalKind(StrEnum):
    DEADLINE = "deadline"
    APPROVAL = "approval"
    PRACTICE = "practice"
    SYSTEM = "system"


class DashboardMatterSummary(BaseModel):
    id: str
    title: str
    status: str
    matter_type: str
    client_name: str | None = None
    case_number: str | None = None
    deadline_count: int = 0
    overdue_deadline_count: int = 0
    next_deadline_title: str | None = None
    next_deadline_date: date | None = None


class DashboardSignal(BaseModel):
    id: str
    kind: DashboardSignalKind
    title: str
    body: str
    priority: int = Field(ge=0, le=100)
    requires_approval: bool = False
    matter_id: str | None = None
    due_date: date | None = None


class DashboardSnapshot(BaseModel):
    generated_at: datetime
    total_matters: int
    active_matters: int
    overdue_deadlines: int
    deadlines_next_7_days: int
    pending_approvals: int
    matters: list[DashboardMatterSummary] = Field(default_factory=list)
    signals: list[DashboardSignal] = Field(default_factory=list)


class DashboardService:
    """Build an attorney-facing dashboard from persisted matter state.

    The service is intentionally read-only. It reports deadlines and workflow state but does
    not perform legal actions, approve requests, or mutate matters.
    """

    def __init__(self, matters: MatterRepository) -> None:
        self.matters = matters

    def snapshot(
        self,
        *,
        today: date | None = None,
        generated_at: datetime | None = None,
        pending_approvals: int = 0,
        extra_signals: tuple[DashboardSignal, ...] = (),
    ) -> DashboardSnapshot:
        today = today or datetime.now(timezone.utc).date()
        generated_at = generated_at or datetime.now(timezone.utc)
        if generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        if pending_approvals < 0:
            raise ValueError("pending_approvals cannot be negative")

        matters = self.matters.list_matters()
        summaries: list[DashboardMatterSummary] = []
        signals = list(extra_signals)
        overdue_total = 0
        upcoming_total = 0

        for matter in matters:
            dated = [deadline for deadline in matter.deadlines if deadline.due_date is not None]
            dated.sort(key=lambda item: item.due_date or date.max)
            overdue = [item for item in dated if item.due_date and item.due_date < today]
            upcoming = [
                item
                for item in dated
                if item.due_date and today <= item.due_date <= today + timedelta(days=7)
            ]
            overdue_total += len(overdue)
            upcoming_total += len(upcoming)

            future = [item for item in dated if item.due_date and item.due_date >= today]
            next_deadline = future[0] if future else None
            summaries.append(
                DashboardMatterSummary(
                    id=matter.id,
                    title=matter.title,
                    status=matter.status,
                    matter_type=matter.matter_type.value,
                    client_name=matter.client_name,
                    case_number=matter.case_number,
                    deadline_count=len(matter.deadlines),
                    overdue_deadline_count=len(overdue),
                    next_deadline_title=next_deadline.title if next_deadline else None,
                    next_deadline_date=next_deadline.due_date if next_deadline else None,
                )
            )

            for deadline in overdue:
                signals.append(
                    self._deadline_signal(
                        matter_id=matter.id,
                        matter_title=matter.title,
                        deadline_title=deadline.title,
                        due_date=deadline.due_date,
                        today=today,
                    )
                )
            for deadline in upcoming:
                signals.append(
                    self._deadline_signal(
                        matter_id=matter.id,
                        matter_title=matter.title,
                        deadline_title=deadline.title,
                        due_date=deadline.due_date,
                        today=today,
                    )
                )

        summaries.sort(
            key=lambda item: (
                item.next_deadline_date or date.max,
                item.title.casefold(),
            )
        )
        signals.sort(key=lambda item: (-item.priority, item.due_date or date.max, item.id))
        return DashboardSnapshot(
            generated_at=generated_at,
            total_matters=len(matters),
            active_matters=sum(item.status.casefold() == "active" for item in matters),
            overdue_deadlines=overdue_total,
            deadlines_next_7_days=upcoming_total,
            pending_approvals=pending_approvals,
            matters=summaries,
            signals=signals,
        )

    @staticmethod
    def _deadline_signal(
        *,
        matter_id: str,
        matter_title: str,
        deadline_title: str,
        due_date: date | None,
        today: date,
    ) -> DashboardSignal:
        if due_date is None:
            raise ValueError("due_date is required for deadline signal")
        delta = (due_date - today).days
        if delta < 0:
            priority = 95
            body = f"Срок истёк {due_date.isoformat()}. Требуется немедленная проверка."
        elif delta == 0:
            priority = 90
            body = "Срок наступает сегодня."
        elif delta <= 3:
            priority = 75
            body = f"До срока осталось {delta} дн."
        else:
            priority = 55
            body = f"Срок наступает {due_date.isoformat()}."
        return DashboardSignal(
            id=f"deadline:{matter_id}:{due_date.isoformat()}:{deadline_title}",
            kind=DashboardSignalKind.DEADLINE,
            title=f"{matter_title}: {deadline_title}",
            body=body,
            priority=priority,
            requires_approval=False,
            matter_id=matter_id,
            due_date=due_date,
        )
