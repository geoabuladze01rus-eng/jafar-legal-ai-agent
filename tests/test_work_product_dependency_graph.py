from datetime import date

from jafar.doctrine_case_impact import DoctrineImpactUrgency, WorkProductKind
from jafar.doctrine_evolution import DoctrineEvent, DoctrineEventType, DoctrineEvolutionTimeline
from jafar.work_product_dependency_graph import (
    FragmentKind,
    WorkProductDependencyGraph,
    WorkProductFragment,
)


def _timeline(event_type: DoctrineEventType) -> DoctrineEvolutionTimeline:
    event = DoctrineEvent(
        event_id=f"event:{event_type.value}",
        occurred_on=date(2026, 8, 28),
        event_type=event_type,
        legal_issue="допустимость доказательств",
        primary_rule_id="rule:old",
        related_rule_id="rule:new",
        authority_ids=("auth-old", "auth-new"),
        summary="verified doctrine event",
        verified=True,
        requires_lawyer_review=True,
    )
    return DoctrineEvolutionTimeline(
        legal_issue="допустимость доказательств",
        events=(event,),
        current_rule_ids=("rule:new",),
        unresolved_rule_pairs=(),
        precedent_requires_review=False,
        requires_lawyer_review=True,
    )


def _fragment(*, rule_ids=("rule:old",), authority_ids=("auth-old",)) -> WorkProductFragment:
    return WorkProductFragment(
        fragment_id="complaint:p3",
        work_product_id="complaint:1",
        work_product_kind=WorkProductKind.COMPLAINT,
        fragment_kind=FragmentKind.ARGUMENT,
        ordinal=3,
        text="Довод о недопустимости доказательства.",
        topic="допустимость доказательств",
        theory_issue_ids=("theory:1",),
        authority_ids=authority_ids,
        rule_ids=rule_ids,
        source_refs=("document:abc:page:4:chunk:1",),
    )


def test_supersession_marks_exact_fragment_stale_and_critical() -> None:
    report = WorkProductDependencyGraph().analyze(
        work_product_id="complaint:1",
        fragments=(_fragment(),),
        doctrine=_timeline(DoctrineEventType.SUPERSESSION),
    )
    assert report.stale_fragment_ids == ("complaint:p3",)
    assert report.critical_fragment_ids == ("complaint:p3",)
    assert report.impacts[0].urgency == DoctrineImpactUrgency.CRITICAL
    assert not WorkProductDependencyGraph.release_ready(report)


def test_narrowing_marks_exact_fragment_stale_high() -> None:
    report = WorkProductDependencyGraph().analyze(
        work_product_id="complaint:1",
        fragments=(_fragment(),),
        doctrine=_timeline(DoctrineEventType.NARROWING),
    )
    assert report.impacts[0].stale is True
    assert report.impacts[0].urgency == DoctrineImpactUrgency.HIGH
    assert not WorkProductDependencyGraph.release_ready(report)


def test_broadening_requires_review_but_not_stale() -> None:
    report = WorkProductDependencyGraph().analyze(
        work_product_id="complaint:1",
        fragments=(_fragment(),),
        doctrine=_timeline(DoctrineEventType.BROADENING),
    )
    assert report.impacts[0].stale is False
    assert report.impacts[0].urgency == DoctrineImpactUrgency.MEDIUM
    assert WorkProductDependencyGraph.release_ready(report)


def test_unrelated_fragment_is_not_flagged() -> None:
    fragment = WorkProductFragment(
        fragment_id="complaint:p7",
        work_product_id="complaint:1",
        work_product_kind=WorkProductKind.COMPLAINT,
        fragment_kind=FragmentKind.ARGUMENT,
        ordinal=7,
        text="Иной процессуальный довод.",
        topic="мера пресечения",
        authority_ids=("other-auth",),
        rule_ids=("other-rule",),
    )
    report = WorkProductDependencyGraph().analyze(
        work_product_id="complaint:1",
        fragments=(fragment,),
        doctrine=_timeline(DoctrineEventType.SUPERSESSION),
    )
    assert report.impacts == ()
    assert report.stale_fragment_ids == ()
    assert WorkProductDependencyGraph.release_ready(report)


def test_dependency_can_match_rule_without_topic_match() -> None:
    fragment = WorkProductFragment(
        fragment_id="motion:p2",
        work_product_id="motion:1",
        work_product_kind=WorkProductKind.MOTION,
        fragment_kind=FragmentKind.ARGUMENT,
        ordinal=2,
        text="Аргумент связан с нормализованным правилом.",
        topic="иной ярлык",
        rule_ids=("rule:old",),
    )
    report = WorkProductDependencyGraph().analyze(
        work_product_id="motion:1",
        fragments=(fragment,),
        doctrine=_timeline(DoctrineEventType.EXCEPTION),
    )
    assert report.impacts[0].fragment_id == "motion:p2"
    assert report.impacts[0].matched_rule_ids == ("rule:old",)
    assert report.impacts[0].urgency == DoctrineImpactUrgency.HIGH
