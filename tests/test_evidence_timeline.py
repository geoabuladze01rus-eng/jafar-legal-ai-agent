from datetime import datetime, timezone

from jafar.evidence_timeline import EvidenceItem, EvidenceTimeline


def test_evidence_timeline_orders_and_links_evidence():
    timeline = EvidenceTimeline().build([
        EvidenceItem("e2", "document", "Протокол", "email", datetime(2026, 8, 22, tzinfo=timezone.utc), "doc-2", "case-1", ("person-1",)),
        EvidenceItem("e1", "recording", "Разговор", "plaud", datetime(2026, 8, 21, tzinfo=timezone.utc), None, "case-1", ("person-1", "entity-1")),
    ])
    assert [item["evidence_id"] for item in timeline["items"]] == ["e1", "e2"]
    assert timeline["evidence_count"] == 2
    assert timeline["cases"] == ["case-1"]
    assert timeline["entities"] == ["entity-1", "person-1"]
