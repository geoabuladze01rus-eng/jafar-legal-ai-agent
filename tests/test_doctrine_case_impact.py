from datetime import date

from jafar.case_theory import CaseTheoryIssue, CaseTheoryReport, TheoryStatus
from jafar.doctrine_case_impact import (
    ActiveWorkProduct,
    DoctrineImpactUrgency,
    DoctrineToCaseImpactEngine,
    WorkProductKind,
)
from jafar.doctrine_evolution import (
    DoctrineEvent,
    DoctrineEventType,
    DoctrineEvolutionTimeline,
)


def _theory(topic: str = "допустимость доказательств") -> CaseTheoryReport:
    issue = CaseTheoryIssue(
        issue_id="theory:1",
        topic=topic,
        statement="Доказательство требует процессуальной проверки",
        position="defense",
        status=TheoryStatus.SUPPORTED,
        claim_ids=("claim:1",),
        evidence_ids=("e:1",),
        source_refs=(),
        reasons=(),
    )
    return CaseTheoryReport(
        issues=(issue,),
        supported_count=1,
        contradicted_count=0,
        unsupported_count=0,
        review_required_count=0,
        requires_human_review=False,
    )


def _timeline(event_type: DoctrineEventType) -> DoctrineEvolutionTimeline:
    event = DoctrineEvent(
        event_id=f"doctrine:{event_type.value}:1",
        occurred_on=date(2026, 8, 28),
        event_type=event_type,
        legal_issue="допустимость доказательств",
        primary_rule_id="rule:1",
        related_rule_id="rule:2",
        authority_ids=("authority:new",),
        summary="verified doctrine change",
        verified=True,
        requires_lawyer_review=True,
    )
    return DoctrineEvolutionTimeline(
        legal_issue="допустимость доказательств",
        events=(event,),
        current_rule_ids=("rule:2",),
        unresolved_rule_pairs=(),
        precedent_requires_review=False,
        requires_lawyer_review=True,
    )


def test_supersession_is_critical_for_matching_case_issue():
    report = DoctrineToCaseImpactEngine().analyze(
        case_id="case:1",
        theory=_theory(),
        doctrine=_timeline(DoctrineEventType.SUPERSESSION),
    )

    assert report.impacts[0].urgency == DoctrineImpactUrgency.CRITICAL
    assert report.critical_issue_ids == ("theory:1",)
    assert not DoctrineToCaseImpactEngine.release_ready(report)


def test_exception_becomes_critical_when_existing_work_product_is_affected():
    product = ActiveWorkProduct(
        work_product_id="motion:1",
        kind=WorkProductKind.MOTION,
        title="Ходатайство",
        topic="допустимость доказательств",
        authority_ids=("authority:new",),
        rule_ids=("rule:1",),
    )
    report = DoctrineToCaseImpactEngine().analyze(
        case_id="case:1",
        theory=_theory(),
        doctrine=_timeline(DoctrineEventType.EXCEPTION),
        work_products=(product,),
    )

    impact = report.impacts[0]
    assert impact.urgency == DoctrineImpactUrgency.CRITICAL
    assert impact.affected_work_product_ids == ("motion:1",)


def test_broadening_without_existing_document_is_medium():
    report = DoctrineToCaseImpactEngine().analyze(
        case_id="case:1",
        theory=_theory(),
        doctrine=_timeline(DoctrineEventType.BROADENING),
    )

    assert report.impacts[0].urgency == DoctrineImpactUrgency.MEDIUM
    assert DoctrineToCaseImpactEngine.release_ready(report)


def test_unrelated_case_topic_gets_no_impact():
    report = DoctrineToCaseImpactEngine().analyze(
        case_id="case:1",
        theory=_theory("мера пресечения"),
        doctrine=_timeline(DoctrineEventType.NARROWING),
    )

    assert report.impacts == ()
    assert report.critical_issue_ids == ()
    assert DoctrineToCaseImpactEngine.release_ready(report)
