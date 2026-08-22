from datetime import datetime, timezone

from jafar.case_intelligence import CaseDeadline, CaseEvent, CaseIntelligence


def test_case_snapshot_orders_events_and_deadlines():
    intelligence = CaseIntelligence()
    snapshot = intelligence.build_snapshot(
        case_id="case-1",
        events=[
            CaseEvent("document", "Первичный документ", datetime(2026, 8, 20, tzinfo=timezone.utc)),
            CaseEvent("hearing", "Судебное заседание", datetime(2026, 8, 22, tzinfo=timezone.utc)),
        ],
        deadlines=[
            CaseDeadline("Проверить срок", datetime(2026, 8, 21, tzinfo=timezone.utc), "plaud", 0.71, True),
            CaseDeadline("Подать документ", datetime(2026, 8, 25, tzinfo=timezone.utc), "court", 1.0),
        ],
    )
    assert snapshot["events"][0]["title"] == "Судебное заседание"
    assert snapshot["deadlines"][0]["title"] == "Проверить срок"
    assert snapshot["requires_human_review"] is True
