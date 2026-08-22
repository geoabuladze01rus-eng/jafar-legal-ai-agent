from jafar.legal_reasoning import LegalReasoningEngine


def test_reasoning_keeps_inferences_grounded_in_evidence():
    result = LegalReasoningEngine().analyze(
        facts=[{"statement": "Договор подписан", "evidence_ids": ["e1"], "confidence": 0.99}],
        evidence=[{"evidence_id": "e1"}],
        risks=[{"title": "Риск просрочки", "severity": "medium", "evidence_ids": ["e1"], "confidence": 0.8}],
        timeline=[{"event_at": "2026-01-01", "title": "Подписание"}],
    )
    assert result["human_review_required"] is True
    assert result["findings"][0]["basis"] == ["e1"]
    assert result["timeline"][0]["title"] == "Подписание"
