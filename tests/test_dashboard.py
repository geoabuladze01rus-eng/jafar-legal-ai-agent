from datetime import date, datetime, timezone

import pytest

from jafar.dashboard import (
    DashboardService,
    DashboardSignal,
    DashboardSignalKind,
)
from jafar.domains import MatterType
from jafar.legal_models import Deadline, Matter
from jafar.matters import MatterStore


def matter(
    matter_id: str,
    title: str,
    deadlines: list[Deadline],
    *,
    status: str = "active",
) -> Matter:
    now = datetime(2026, 8, 28, 12, tzinfo=timezone.utc)
    return Matter(
        id=matter_id,
        title=title,
        matter_type=MatterType.CRIMINAL,
        status=status,
        deadlines=deadlines,
        created_at=now,
        updated_at=now,
    )


def test_dashboard_uses_real_matter_deadlines_and_orders_urgent_signals_first() -> None:
    store = MatterStore()
    store.create(
        matter(
            "case-1",
            "Павлик",
            [
                Deadline(title="Подать жалобу", due_date=date(2026, 8, 27)),
                Deadline(title="Подготовиться к заседанию", due_date=date(2026, 8, 30)),
            ],
        )
    )
    store.create(
        matter(
            "case-2",
            "Другое дело",
            [Deadline(title="Проверить материалы", due_date=date(2026, 9, 10))],
        )
    )

    snapshot = DashboardService(store).snapshot(
        today=date(2026, 8, 28),
        generated_at=datetime(2026, 8, 28, 13, tzinfo=timezone.utc),
    )

    assert snapshot.total_matters == 2
    assert snapshot.active_matters == 2
    assert snapshot.overdue_deadlines == 1
    assert snapshot.deadlines_next_7_days == 1
    assert snapshot.signals[0].kind == DashboardSignalKind.DEADLINE
    assert snapshot.signals[0].priority == 95
    assert snapshot.signals[0].matter_id == "case-1"
    assert snapshot.matters[0].id == "case-1"
    assert snapshot.matters[0].next_deadline_date == date(2026, 8, 30)


def test_dashboard_does_not_treat_undated_deadline_as_overdue() -> None:
    store = MatterStore()
    store.create(
        matter(
            "case-1",
            "Дело",
            [Deadline(title="Уточнить срок", due_date=None)],
        )
    )

    snapshot = DashboardService(store).snapshot(today=date(2026, 8, 28))

    assert snapshot.overdue_deadlines == 0
    assert snapshot.deadlines_next_7_days == 0
    assert snapshot.signals == []
    assert snapshot.matters[0].deadline_count == 1


def test_closed_matter_deadlines_do_not_create_false_urgent_signals() -> None:
    store = MatterStore()
    store.create(
        matter(
            "closed-case",
            "Завершённое дело",
            [Deadline(title="Исторический срок", due_date=date(2020, 1, 1))],
            status="closed",
        )
    )

    snapshot = DashboardService(store).snapshot(today=date(2026, 8, 28))

    assert snapshot.total_matters == 1
    assert snapshot.active_matters == 0
    assert snapshot.overdue_deadlines == 0
    assert snapshot.deadlines_next_7_days == 0
    assert snapshot.signals == []
    assert snapshot.matters[0].next_deadline_date is None


def test_dashboard_caps_signal_payload_after_priority_sorting() -> None:
    signals = tuple(
        DashboardSignal(
            id=f"signal-{index}",
            kind=DashboardSignalKind.SYSTEM,
            title=f"Signal {index}",
            body="review",
            priority=index % 101,
        )
        for index in range(150)
    )

    snapshot = DashboardService(MatterStore()).snapshot(extra_signals=signals)

    assert len(snapshot.signals) == DashboardService.MAX_SIGNALS
    assert snapshot.signals[0].priority >= snapshot.signals[-1].priority


def test_dashboard_validates_timestamp_and_approval_count() -> None:
    service = DashboardService(MatterStore())

    with pytest.raises(ValueError, match="timezone-aware"):
        service.snapshot(generated_at=datetime(2026, 8, 28, 13))

    with pytest.raises(ValueError, match="cannot be negative"):
        service.snapshot(pending_approvals=-1)
