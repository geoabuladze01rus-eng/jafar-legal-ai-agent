from jafar.legal_entity_risk import LegalEntityRiskEngine, RiskSignal


def test_risk_engine_aggregates_source_signals():
    result = LegalEntityRiskEngine().assess([
        RiskSignal("fssp", "debt", "Исполнительные производства", "high", 1.0, ("fssp-1",)),
        RiskSignal("financials", "loss", "Убыток", "medium", 0.5, ("fin-1",)),
    ])
    assert result["risk_level"] == "high"
    assert result["requires_human_review"] is True
    assert len(result["signals"]) == 2
