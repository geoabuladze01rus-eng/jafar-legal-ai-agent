from datetime import UTC, datetime

from jafar.case_intelligence import CaseDeadline, CaseEvent, CaseIntelligence


def test_case_snapshot_orders_events_and_deadlines():
    intelligence = CaseIntelligence()
    snapshot = intelligence.build_snapshot(
        case_id="case-1",
        events=[
            CaseEvent("document", "Первичный документ", datetime(2026, 8, 20, tzinfo=UTC)),
            CaseEvent("hearing", "Судебное заседание", datetime(2026, 8, 22, tzinfo=UTC)),
        ],
        deadlines=[
            CaseDeadline("Проверить срок", datetime(2026, 8, 21, tzinfo=UTC), "plaud", 0.71, True),
            CaseDeadline("Подать документ", datetime(2026, 8, 25, tzinfo=UTC), "court", 1.0),
        ],
    )
    assert snapshot["events"][0]["title"] == "Судебное заседание"
    assert snapshot["deadlines"][0]["title"] == "Проверить срок"
    assert snapshot["requires_human_review"] is True
