from jafar.holding_rule_normalization import NormalizedLegalRule
from jafar.legal_rule_conflict_graph import (
    LegalRuleConflictGraph,
    RuleRelation,
    RuleRelationType,
)


def _rule(rule_id: str, semantic_key: str, rule: str) -> NormalizedLegalRule:
    return NormalizedLegalRule(
        rule_id=rule_id,
        authority_id=f"authority:{rule_id}",
        legal_issue="допустимость доказательств",
        rule=rule,
        conditions=(),
        exceptions=(),
        consequence="",
        source_refs=(f"source:{rule_id}",),
        semantic_key=semantic_key,
        source_holding_text=rule,
    )


def test_same_semantic_key_is_same_rule_without_external_relation():
    left = _rule("r1", "same", "Доказательство требует проверки")
    right = _rule("r2", "same", "Доказательство требует проверки")

    report = LegalRuleConflictGraph().build(
        legal_issue="допустимость доказательств",
        rules=(left, right),
    )

    assert report.edges[0].relation == RuleRelationType.SAME_RULE
    assert report.edges[0].verified is True
    assert report.unresolved_pairs == ()
    assert LegalRuleConflictGraph.release_ready(report) is True


def test_materially_different_rules_without_verified_relation_are_unresolved():
    left = _rule("r1", "a", "Правило A")
    right = _rule("r2", "b", "Правило B")

    report = LegalRuleConflictGraph().build(
        legal_issue="допустимость доказательств",
        rules=(left, right),
    )

    assert report.edges == ()
    assert report.unresolved_pairs == (("r1", "r2"),)
    assert report.requires_human_review is True
    assert LegalRuleConflictGraph.release_ready(report) is False


def test_verified_conflict_blocks_release():
    left = _rule("r1", "a", "Правило A")
    right = _rule("r2", "b", "Правило B")
    relation = RuleRelation(
        left_rule_id="r1",
        right_rule_id="r2",
        relation=RuleRelationType.CONFLICT,
        explanation="Проверенный конфликт правовых правил.",
        verified=True,
    )

    report = LegalRuleConflictGraph().build(
        legal_issue="допустимость доказательств",
        rules=(left, right),
        relations=(relation,),
    )

    assert report.edges[0].relation == RuleRelationType.CONFLICT
    assert report.requires_human_review is True
    assert LegalRuleConflictGraph.release_ready(report) is False


def test_unverified_relation_cannot_change_graph():
    left = _rule("r1", "a", "Правило A")
    right = _rule("r2", "b", "Правило B")
    relation = RuleRelation(
        left_rule_id="r1",
        right_rule_id="r2",
        relation=RuleRelationType.SUPERSEDED,
        explanation="Model guess",
        verified=False,
    )

    report = LegalRuleConflictGraph().build(
        legal_issue="допустимость доказательств",
        rules=(left, right),
        relations=(relation,),
    )

    assert report.edges == ()
    assert report.unresolved_pairs == (("r1", "r2"),)


def test_verified_narrower_relation_can_pass_release():
    left = _rule("r1", "a", "Общее правило")
    right = _rule("r2", "b", "Более узкое правило")
    relation = RuleRelation(
        left_rule_id="r1",
        right_rule_id="r2",
        relation=RuleRelationType.NARROWER,
        explanation="Проверенная последующая позиция ограничивает область применения.",
        verified=True,
    )

    report = LegalRuleConflictGraph().build(
        legal_issue="допустимость доказательств",
        rules=(left, right),
        relations=(relation,),
    )

    assert report.edges[0].relation == RuleRelationType.NARROWER
    assert report.unresolved_pairs == ()
    assert LegalRuleConflictGraph.release_ready(report) is True
