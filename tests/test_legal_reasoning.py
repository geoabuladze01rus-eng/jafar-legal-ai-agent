from jafar.legal_reasoning import LegalReasoningEngine


def test_reasoning_keeps_inference_grounded_in_evidence():
    result = LegalReasoningEngine().analyze(
        facts=[{"statement": "Документ получен 21 августа", "evidence_ids": ["e1"], "confidence": 0.99}],
        evidence=[{"evidence_id": "e1", "source": "email"}],
        risks=[{"title": "Недостаточно данных", "evidence_ids": ["missing"], "confidence": 0.4, "severity": "medium"}],
    )
    assert result["human_review_required"] is True
    assert result["findings"][0]["basis"] == ["e1"]
    assert result["findings"][1]["basis"] == []
    assert result["findings"][1]["requires_human_review"] is True
