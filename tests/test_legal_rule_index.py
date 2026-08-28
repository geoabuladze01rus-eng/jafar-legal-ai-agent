from jafar.holding_rule_normalization import NormalizedLegalRule
from jafar.legal_rule_index import LegalRuleConcept, LegalRuleIndex, LegalRuleOntology


def rule(rule_id: str, issue: str, text: str) -> NormalizedLegalRule:
    return NormalizedLegalRule(
        rule_id=rule_id,
        authority_id=f"authority:{rule_id}",
        legal_issue=issue,
        rule=text,
        conditions=(),
        exceptions=(),
        consequence="",
        source_refs=("page:1",),
        semantic_key=f"key:{rule_id}",
        source_holding_text=text,
    )


def test_curated_aliases_match_different_wording() -> None:
    issue_ontology = LegalRuleOntology(
        (
            LegalRuleConcept(
                concept_id="issue:evidence-admissibility",
                canonical_label="Допустимость доказательств",
                aliases=("Вопрос допустимости доказательств",),
            ),
        )
    )
    rule_ontology = LegalRuleOntology(
        (
            LegalRuleConcept(
                concept_id="rule:evidence-review",
                canonical_label="Доказательство подлежит процессуальной проверке",
                aliases=("Суд обязан проверить доказательство процессуально",),
            ),
        )
    )
    index = LegalRuleIndex(issue_ontology=issue_ontology, rule_ontology=rule_ontology)
    left = index.add(
        rule(
            "r1",
            "Допустимость доказательств",
            "Доказательство подлежит процессуальной проверке",
        )
    )
    right = index.add(
        rule(
            "r2",
            "Вопрос допустимости доказательств",
            "Суд обязан проверить доказательство процессуально",
        )
    )

    match = index.match(left.rule.rule_id, right.rule.rule_id)
    assert match.equivalent is True
    assert match.same_issue is True
    assert match.same_rule_concept is True


def test_unknown_wording_is_not_guessed() -> None:
    ontology = LegalRuleOntology(
        (LegalRuleConcept(concept_id="known", canonical_label="Известное правило"),)
    )
    assert ontology.resolve("Похожее, но не зарегистрированное правило") is None


def test_ambiguous_alias_is_rejected() -> None:
    try:
        LegalRuleOntology(
            (
                LegalRuleConcept("a", "Правило А", aliases=("Общий псевдоним",)),
                LegalRuleConcept("b", "Правило Б", aliases=("Общий псевдоним",)),
            )
        )
    except ValueError as exc:
        assert "Ambiguous ontology label" in str(exc)
    else:
        raise AssertionError("ambiguous ontology alias must fail closed")
