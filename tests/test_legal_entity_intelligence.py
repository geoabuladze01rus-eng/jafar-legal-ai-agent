from jafar.legal_entity_intelligence import LegalEntityIntelligence, SourceFinding


def test_entity_profile_scores_cross_source_risks():
    service = LegalEntityIntelligence()
    profile = service.build_profile(
        [
            SourceFinding(
                "fedresurs", "found", "Банкротство", {"bankruptcy": True}
            ),
            SourceFinding(
                "fssp", "found", "Исполнительные производства", {"debt_amount": 2_000_000}
            ),
            SourceFinding("kad", "found", "Арбитраж", {"case_count": 25}),
            SourceFinding("bo", "found", "Финансы", {"revenue": 0, "net_loss": 100_000}),
            SourceFinding("egrul", "no_data", "ЕГРЮЛ", {}),
        ]
    )

    assert profile["risk_level"] == "critical"
    assert profile["risk_score"] == 100
    assert profile["sources_no_data"] == 1
    assert any(item["code"] == "bankruptcy" for item in profile["risks"])
    assert any(item["code"] == "enforcement_debt" for item in profile["risks"])


def test_no_data_is_not_a_negative_finding():
    profile = LegalEntityIntelligence().build_profile(
        [SourceFinding("fssp", "no_data", "ФССП", {})]
    )
    assert profile["risk_level"] == "unknown"
    assert profile["sources_no_data"] == 1
    assert profile["sources_negative"] == 0
