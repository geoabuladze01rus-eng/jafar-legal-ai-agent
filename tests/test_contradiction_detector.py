from jafar.contradiction_detector import ContradictionGapDetector


def test_detector_finds_conflicting_claims():
    detector = ContradictionGapDetector()
    items = detector.compare_claims([
        {"topic": "date", "statement": "Событие произошло 10 августа", "position": "2026-08-10", "evidence_ids": ["e1"]},
        {"topic": "date", "statement": "Событие произошло 12 августа", "position": "2026-08-12", "evidence_ids": ["e2"]},
    ])
    assert len(items) == 1
    assert items[0].severity == "high"
    assert set(items[0].evidence_ids) == {"e1", "e2"}


def test_detector_finds_missing_required_topics():
    items = ContradictionGapDetector().find_gaps(
        [{"topic": "date", "statement": "10 августа"}],
        ["date", "document_origin", "witness_identity"],
    )
    assert [item.topic for item in items] == ["document_origin", "witness_identity"]
