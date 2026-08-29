from datetime import date

from jafar.authority_applicability import AuthorityWeight
from jafar.precedent_freshness import (
    PrecedentFreshnessEngine,
    PrecedentRecord,
    PrecedentRelation,
    PrecedentTreatment,
)
from jafar.precedent_policy import PrecedentReleasePolicy


def record(
    authority_id: str,
    decided_on: date,
    proposition: str,
    weight: AuthorityWeight = AuthorityWeight.HIGH,
) -> PrecedentRecord:
    return PrecedentRecord(
        authority_id=authority_id,
        citation=authority_id,
        topic="topic",
        proposition=proposition,
        decided_on=decided_on,
        weight=weight,
        authority_type="court_position",
        source_url=f"https://example.test/{authority_id}",
        source_fingerprint=f"fp-{authority_id}",
    )


def test_conflicting_precedent_blocks_release() -> None:
    older = record("old", date(2024, 1, 1), "A")
    newer = record("new", date(2026, 1, 1), "B")
    relation = PrecedentRelation(
        earlier_id="old",
        later_id="new",
        treatment=PrecedentTreatment.CONFLICTING,
        explanation="conflict",
        verified=True,
    )
    report = PrecedentFreshnessEngine().build(topic="topic", precedents=(older, newer), relations=(relation,))
    decision = PrecedentReleasePolicy().decide(report)
    assert decision.ready is False
    assert "old" in decision.blocked_authority_ids


def test_confirmed_consistent_chain_can_release() -> None:
    older = record("old", date(2024, 1, 1), "A", AuthorityWeight.BINDING)
    newer = record("new", date(2026, 1, 1), "A")
    relation = PrecedentRelation(
        earlier_id="old",
        later_id="new",
        treatment=PrecedentTreatment.CONSISTENT,
        explanation="consistent",
        verified=True,
    )
    report = PrecedentFreshnessEngine().build(topic="topic", precedents=(older, newer), relations=(relation,))
    decision = PrecedentReleasePolicy().decide(report)
    assert decision.ready is True
    assert decision.blocked_authority_ids == ()
