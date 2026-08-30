from datetime import date

from jafar.doctrine_evolution import DoctrineEventType, DoctrineEvolutionEngine
from jafar.holding_rule_normalization import NormalizedLegalRule
from jafar.legal_rule_conflict_graph import LegalRuleConflictGraph, RuleRelation, RuleRelationType
from jafar.precedent_freshness import (
    AuthorityWeight,
    PrecedentFreshnessEngine,
    PrecedentRecord,
    PrecedentRelation,
    PrecedentTreatment,
)


def _rule(rule_id: str, authority_id: str, semantic_key: str) -> NormalizedLegalRule:
    return NormalizedLegalRule(
        rule_id=rule_id,
        authority_id=authority_id,
        legal_issue="допустимость доказательств",
        rule=f"rule {rule_id}",
        conditions=(),
        exceptions=(),
        consequence="",
        source_refs=(f"source:{authority_id}",),
        semantic_key=semantic_key,
        source_holding_text=f"holding {rule_id}",
    )


def _precedent(authority_id: str, decided_on: date) -> PrecedentRecord:
    return PrecedentRecord(
        authority_id=authority_id,
        citation=authority_id,
        topic="допустимость доказательств",
        proposition=authority_id,
        decided_on=decided_on,
        weight=AuthorityWeight.HIGH,
        authority_type="supreme_court",
        source_url=f"https://vsrf.ru/{authority_id}",
        source_fingerprint=f"fp-{authority_id}",
    )


def test_builds_chronological_doctrine_events() -> None:
    first = _rule("r1", "a1", "k1")
    second = _rule("r2", "a2", "k2")
    graph = LegalRuleConflictGraph().build(
        legal_issue=first.legal_issue,
        rules=(first, second),
        relations=(
            RuleRelation(
                left_rule_id="r1",
                right_rule_id="r2",
                relation=RuleRelationType.NARROWER,
                explanation="Later rule narrows the earlier rule.",
                verified=True,
            ),
        ),
    )
    precedent = PrecedentFreshnessEngine().build(
        topic=first.legal_issue,
        precedents=(
            _precedent("a1", date(2024, 1, 10)),
            _precedent("a2", date(2025, 2, 20)),
        ),
        relations=(
            PrecedentRelation(
                earlier_id="a1",
                later_id="a2",
                treatment=PrecedentTreatment.LIMITING,
                explanation="Later authority limits the first.",
                verified=True,
            ),
        ),
    )
    timeline = DoctrineEvolutionEngine().build(rule_graph=graph, precedent=precedent)
    narrowing = next(event for event in timeline.events if event.event_type == DoctrineEventType.NARROWING)
    assert narrowing.occurred_on == date(2025, 2, 20)
    assert narrowing.verified is True


def test_unresolved_rule_pair_blocks_release() -> None:
    graph = LegalRuleConflictGraph().build(
        legal_issue="допустимость доказательств",
        rules=(_rule("r1", "a1", "k1"), _rule("r2", "a2", "k2")),
    )
    timeline = DoctrineEvolutionEngine().build(rule_graph=graph)
    assert timeline.unresolved_rule_pairs == (("r1", "r2"),)
    assert DoctrineEvolutionEngine.release_ready(timeline) is False


def test_conflict_blocks_release() -> None:
    graph = LegalRuleConflictGraph().build(
        legal_issue="допустимость доказательств",
        rules=(_rule("r1", "a1", "k1"), _rule("r2", "a2", "k2")),
        relations=(
            RuleRelation(
                left_rule_id="r1",
                right_rule_id="r2",
                relation=RuleRelationType.CONFLICT,
                explanation="Verified conflict.",
                verified=True,
            ),
        ),
    )
    timeline = DoctrineEvolutionEngine().build(rule_graph=graph)
    assert any(event.event_type == DoctrineEventType.CONFLICT for event in timeline.events)
    assert DoctrineEvolutionEngine.release_ready(timeline) is False


def test_same_rule_confirmation_can_release() -> None:
    graph = LegalRuleConflictGraph().build(
        legal_issue="допустимость доказательств",
        rules=(_rule("r1", "a1", "same"), _rule("r2", "a2", "same")),
    )
    timeline = DoctrineEvolutionEngine().build(rule_graph=graph)
    assert any(event.event_type == DoctrineEventType.CONFIRMATION for event in timeline.events)
    assert DoctrineEvolutionEngine.release_ready(timeline) is True


def test_superseded_rule_removed_from_current_set() -> None:
    graph = LegalRuleConflictGraph().build(
        legal_issue="допустимость доказательств",
        rules=(_rule("r1", "a1", "k1"), _rule("r2", "a2", "k2")),
        relations=(
            RuleRelation(
                left_rule_id="r1",
                right_rule_id="r2",
                relation=RuleRelationType.SUPERSEDED,
                explanation="r2 supersedes r1.",
                verified=True,
            ),
        ),
    )
    timeline = DoctrineEvolutionEngine().build(rule_graph=graph)
    assert "r1" not in timeline.current_rule_ids
    assert "r2" in timeline.current_rule_ids
    assert DoctrineEvolutionEngine.release_ready(timeline) is False
