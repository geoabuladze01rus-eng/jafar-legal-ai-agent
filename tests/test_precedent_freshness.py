from datetime import date

from jafar.authority_applicability import AuthorityWeight
from jafar.precedent_freshness import (
    FreshnessStatus,
    PrecedentFreshnessEngine,
    PrecedentRecord,
    PrecedentRelation,
    PrecedentTreatment,
)


def precedent(authority_id: str, decided_on: date, weight: AuthorityWeight, proposition: str) -> PrecedentRecord:
    return PrecedentRecord(
        authority_id=authority_id,
        citation=authority_id,
        topic="evidence",
        proposition=proposition,
        decided_on=decided_on,
        weight=weight,
        authority_type="court_position",
        source_url=f"https://example.test/{authority_id}",
        source_fingerprint=f"fp-{authority_id}",
    )


def test_later_verified_conflict_flags_earlier_precedent() -> None:
    older = precedent("older", date(2024, 1, 1), AuthorityWeight.HIGH, "Требуется A")
    newer = precedent("newer", date(2026, 1, 1), AuthorityWeight.HIGH, "A не требуется")
    relation = PrecedentRelation(
        earlier_id="older",
        later_id="newer",
        treatment=PrecedentTreatment.CONFLICTING,
        explanation="Поздняя позиция расходится с ранней.",
        verified=True,
    )
    report = PrecedentFreshnessEngine().build(topic="evidence", precedents=(older, newer), relations=(relation,))
    by_id = {item.precedent.authority_id: item for item in report.items}
    assert by_id["older"].status == FreshnessStatus.CONFLICTING
    assert report.requires_human_review is True


def test_later_date_does_not_automatically_beat_binding_authority() -> None:
    binding = precedent("binding", date(2022, 1, 1), AuthorityWeight.BINDING, "Правило A")
    later = precedent("later", date(2026, 1, 1), AuthorityWeight.PERSUASIVE, "Правило B")
    relation = PrecedentRelation(
        earlier_id="binding",
        later_id="later",
        treatment=PrecedentTreatment.CONSISTENT,
        explanation="Поздний акт не отменяет обязательную позицию.",
        verified=True,
    )
    report = PrecedentFreshnessEngine().build(topic="evidence", precedents=(binding, later), relations=(relation,))
    by_id = {item.precedent.authority_id: item for item in report.items}
    assert by_id["binding"].status == FreshnessStatus.OLDER_BUT_CONTROLLING
    assert by_id["binding"].freshness_rank > by_id["later"].freshness_rank


def test_superseding_relation_marks_old_position_superseded() -> None:
    older = precedent("old", date(2020, 1, 1), AuthorityWeight.HIGH, "Старое правило")
    newer = precedent("new", date(2026, 1, 1), AuthorityWeight.HIGH, "Новое правило")
    relation = PrecedentRelation(
        earlier_id="old",
        later_id="new",
        treatment=PrecedentTreatment.SUPERSEDING,
        explanation="Новая позиция прямо заменяет старую.",
        verified=True,
    )
    report = PrecedentFreshnessEngine().build(topic="evidence", precedents=(older, newer), relations=(relation,))
    assert {item.precedent.authority_id: item.status for item in report.items}["old"] == FreshnessStatus.SUPERSEDED


def test_unverified_relation_cannot_change_status() -> None:
    older = precedent("old", date(2024, 1, 1), AuthorityWeight.HIGH, "A")
    newer = precedent("new", date(2026, 1, 1), AuthorityWeight.HIGH, "B")
    relation = PrecedentRelation(
        earlier_id="old",
        later_id="new",
        treatment=PrecedentTreatment.SUPERSEDING,
        explanation="Model-only suggestion",
        verified=False,
    )
    report = PrecedentFreshnessEngine().build(topic="evidence", precedents=(older, newer), relations=(relation,))
    by_id = {item.precedent.authority_id: item for item in report.items}
    assert by_id["old"].status == FreshnessStatus.REVIEW_REQUIRED


def test_unresolved_pair_is_exposed_for_followup_verification() -> None:
    left = precedent("a", date(2024, 1, 1), AuthorityWeight.HIGH, "A")
    right = precedent("b", date(2026, 1, 1), AuthorityWeight.HIGH, "B")
    unresolved = PrecedentFreshnessEngine().detect_unresolved_pairs(
        topic="evidence",
        precedents=(left, right),
        relations=(),
    )
    assert unresolved == (("a", "b"),)
