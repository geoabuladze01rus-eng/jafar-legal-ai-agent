from jafar.holding_rule_normalization import HoldingRuleNormalizer, RuleNormalizationInput
from jafar.legal_holding_verifier import HoldingStatus, HoldingVerificationResult
from jafar.legal_proposition_extractor import PropositionCandidate


def verified_holding(text: str) -> HoldingVerificationResult:
    proposition = PropositionCandidate(text=text, confidence=0.55, rationale="test")
    return HoldingVerificationResult(
        proposition=proposition,
        status=HoldingStatus.VERIFIED_HOLDING,
        confidence=0.82,
        reasons=("verified",),
        may_enter_holding_base=True,
    )


def test_normalizes_verified_holding_into_rule_structure() -> None:
    normalizer = HoldingRuleNormalizer()
    result = normalizer.normalize(
        RuleNormalizationInput(
            holding=verified_holding("Судебная коллегия указала, что доказательство подлежит проверке."),
            authority_id="vs:1",
            legal_issue="Допустимость доказательств",
            rule="Доказательство подлежит процессуальной проверке",
            conditions=("Есть возражение стороны",),
            exceptions=("Исключение прямо установлено законом",),
            consequence="Суд должен дать мотивированную оценку",
            source_refs=("page:4", "page:4"),
        )
    )

    assert result.legal_issue == "Допустимость доказательств"
    assert result.conditions == ("Есть возражение стороны",)
    assert result.source_refs == ("page:4",)
    assert result.rule_id.startswith("rule:vs:1:")
    assert result.requires_lawyer_review is True


def test_rejects_non_verified_holding() -> None:
    proposition = PropositionCandidate(text="Защитник указал...", confidence=0.4, rationale="test")
    holding = HoldingVerificationResult(
        proposition=proposition,
        status=HoldingStatus.PARTY_ARGUMENT,
        confidence=0.95,
        reasons=("party",),
        may_enter_holding_base=False,
    )

    try:
        HoldingRuleNormalizer().normalize(
            RuleNormalizationInput(
                holding=holding,
                authority_id="vs:2",
                legal_issue="Допустимость доказательств",
                rule="Некоторое правило",
            )
        )
    except ValueError as exc:
        assert "verified holdings" in str(exc)
    else:
        raise AssertionError("non-verified holding must be rejected")


def test_missing_rule_is_not_inferred() -> None:
    try:
        HoldingRuleNormalizer().normalize(
            RuleNormalizationInput(
                holding=verified_holding("Судебная коллегия указала соответствующий вывод."),
                authority_id="vs:3",
                legal_issue="Меры пресечения",
                rule="",
            )
        )
    except ValueError as exc:
        assert "rule is required" in str(exc)
    else:
        raise AssertionError("missing rule must not be inferred")


def test_semantic_key_ignores_spacing_case_and_condition_order() -> None:
    left = HoldingRuleNormalizer.semantic_key(
        legal_issue="Допустимость доказательств",
        rule="Доказательство подлежит проверке",
        conditions=("Условие Б", "Условие А"),
        consequence="Мотивированная оценка",
    )
    right = HoldingRuleNormalizer.semantic_key(
        legal_issue="  ДОПУСТИМОСТЬ   ДОКАЗАТЕЛЬСТВ ",
        rule="доказательство подлежит проверке!",
        conditions=("условие а", "условие б"),
        consequence="мотивированная оценка",
    )

    assert left == right


def test_materially_different_rules_do_not_collapse() -> None:
    first = HoldingRuleNormalizer.semantic_key(
        legal_issue="Меры пресечения",
        rule="Домашний арест требует оценки оснований",
    )
    second = HoldingRuleNormalizer.semantic_key(
        legal_issue="Меры пресечения",
        rule="Заключение под стражу применяется автоматически",
    )

    assert first != second
