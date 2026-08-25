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
    assert result["evidence_gaps"] == []
    assert result["evidence_coverage"] == {
        "grounded_findings": 2,
        "ungrounded_findings": 0,
        "missing_evidence_references": 0,
    }


def test_missing_fact_evidence_is_normalized_and_reported():
    result = LegalReasoningEngine().analyze(
        facts=[
            {
                "statement": "Платёж произведён",
                "evidence_ids": [7, " missing ", 7, None, {"invalid": True}],
                "confidence": "1.4",
            }
        ],
        evidence=[{"evidence_id": 7}],
    )

    finding = result["findings"][0]
    assert finding["basis"] == ["7"]
    assert finding["confidence"] == 1.0
    assert finding["metadata"]["missing_evidence_ids"] == ["missing"]
    assert result["evidence_gaps"][0]["kind"] == "missing_referenced_evidence"
    assert result["evidence_gaps"][0]["metadata"] == {
        "source_kind": "fact",
        "missing_evidence_ids": ["missing"],
    }
    assert result["evidence_coverage"] == {
        "grounded_findings": 1,
        "ungrounded_findings": 0,
        "missing_evidence_references": 1,
    }


def test_fact_without_evidence_is_explicitly_ungrounded():
    result = LegalReasoningEngine().analyze(
        facts=[{"statement": "Неподтверждённое утверждение", "confidence": -0.5}],
        evidence=[],
    )

    assert result["findings"][0]["confidence"] == 0.0
    assert result["findings"][0]["metadata"]["missing_evidence_ids"] == []
    assert result["evidence_gaps"][0]["kind"] == "ungrounded_fact"
    assert result["evidence_coverage"] == {
        "grounded_findings": 0,
        "ungrounded_findings": 1,
        "missing_evidence_references": 0,
    }


def test_risk_without_evidence_is_explicitly_ungrounded_and_safe():
    result = LegalReasoningEngine().analyze(
        facts=[],
        evidence=[None, {"evidence_id": {"invalid": True}}],
        risks=[
            {
                "title": "Неподтверждённый риск",
                "evidence_ids": {"malformed": "container"},
                "confidence": "not-a-number",
                "severity": "high",
            }
        ],
    )

    finding = result["findings"][0]
    assert finding["basis"] == []
    assert finding["confidence"] == 0.0
    assert finding["metadata"] == {
        "severity": "high",
        "missing_evidence_ids": [],
    }
    assert result["evidence_gaps"][0]["kind"] == "ungrounded_risk"
    assert result["evidence_coverage"]["ungrounded_findings"] == 1


def test_risk_with_missing_numeric_reference_is_reported():
    result = LegalReasoningEngine().analyze(
        facts=[],
        evidence=[{"evidence_id": 1}],
        risks=[{"title": "Риск", "evidence_ids": 2, "confidence": float("inf")}],
    )

    assert result["findings"][0]["basis"] == []
    assert result["findings"][0]["confidence"] == 0.0
    assert result["findings"][0]["metadata"]["missing_evidence_ids"] == ["2"]
    gap = result["evidence_gaps"][0]
    assert gap["kind"] == "missing_referenced_evidence"
    assert gap["metadata"]["source_kind"] == "risk"
    assert gap["metadata"]["missing_evidence_ids"] == ["2"]
    assert result["evidence_coverage"]["missing_evidence_references"] == 1


def test_defensive_helpers_reject_malformed_values_without_crashing():
    engine = LegalReasoningEngine()

    assert engine._normalize_ids(" evidence-1 ") == ("evidence-1",)
    assert engine._normalize_ids([1, 1.0, 1.5, True, None, [], {}]) == ("1", "1.5")
    assert engine._normalize_ids({"evidence_id": "not-a-list"}) == ()
    assert engine._confidence(None) == 0.0
    assert engine._confidence(float("nan")) == 0.0
    assert engine._confidence("0.75") == 0.75
