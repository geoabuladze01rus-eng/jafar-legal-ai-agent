from jafar.doctrine_case_impact import DoctrineImpactUrgency, WorkProductKind
from jafar.safe_fragment_redrafting import (
    RedraftOptionKind,
    SafeFragmentRedraftingEngine,
)
from jafar.work_product_dependency_graph import (
    FragmentDependencyImpact,
    FragmentKind,
    WorkProductDependencyReport,
    WorkProductFragment,
)


def _fragment() -> WorkProductFragment:
    return WorkProductFragment(
        fragment_id="complaint:p3",
        work_product_id="complaint:1",
        work_product_kind=WorkProductKind.COMPLAINT,
        fragment_kind=FragmentKind.ARGUMENT,
        ordinal=3,
        text="Старый довод, основанный на прежней позиции Верховного Суда.",
        topic="допустимость доказательств",
        authority_ids=("authority:old",),
        rule_ids=("rule:old",),
        source_refs=("evidence:1",),
    )


def _report(*, stale: bool, urgency: DoctrineImpactUrgency, reason: str) -> WorkProductDependencyReport:
    impact = FragmentDependencyImpact(
        fragment_id="complaint:p3",
        work_product_id="complaint:1",
        doctrine_event_ids=("doctrine:1",),
        matched_authority_ids=("authority:old",),
        matched_rule_ids=("rule:old",),
        urgency=urgency,
        reasons=(reason,),
        stale=stale,
    )
    return WorkProductDependencyReport(
        work_product_id="complaint:1",
        impacts=(impact,),
        stale_fragment_ids=(("complaint:p3",) if stale else ()),
        critical_fragment_ids=(("complaint:p3",) if urgency == DoctrineImpactUrgency.CRITICAL else ()),
        requires_lawyer_review=True,
    )


def test_stale_fragment_preserves_original_and_blocks_auto_apply() -> None:
    engine = SafeFragmentRedraftingEngine()
    report = engine.prepare(
        dependency_report=_report(
            stale=True,
            urgency=DoctrineImpactUrgency.CRITICAL,
            reason="Фрагмент зависит от правила, которое подтверждённо заменено/преодолено.",
        ),
        fragments=(_fragment(),),
    )
    packet = report.packets[0]
    assert packet.original_text == _fragment().text
    assert packet.source_refs == ("evidence:1",)
    assert packet.may_auto_apply is False
    assert packet.requires_lawyer_approval is True
    assert RedraftOptionKind.REPLACE_AUTHORITY in {item.kind for item in packet.options}
    assert engine.release_ready(report) is False


def test_narrowing_adds_narrow_argument_option() -> None:
    engine = SafeFragmentRedraftingEngine()
    report = engine.prepare(
        dependency_report=_report(
            stale=True,
            urgency=DoctrineImpactUrgency.HIGH,
            reason="Область применения правила, на котором основан фрагмент, подтверждённо сужена.",
        ),
        fragments=(_fragment(),),
    )
    kinds = {item.kind for item in report.packets[0].options}
    assert RedraftOptionKind.NARROW_ARGUMENT in kinds


def test_conflict_requires_human_research() -> None:
    engine = SafeFragmentRedraftingEngine()
    report = engine.prepare(
        dependency_report=_report(
            stale=True,
            urgency=DoctrineImpactUrgency.CRITICAL,
            reason="Фрагмент зависит от правила, по которому имеется подтверждённый конфликт.",
        ),
        fragments=(_fragment(),),
    )
    kinds = {item.kind for item in report.packets[0].options}
    assert RedraftOptionKind.HUMAN_RESEARCH_REQUIRED in kinds


def test_low_risk_fragment_does_not_create_redraft_packet() -> None:
    engine = SafeFragmentRedraftingEngine()
    report = engine.prepare(
        dependency_report=_report(
            stale=False,
            urgency=DoctrineImpactUrgency.LOW,
            reason="Связанная доктрина подтверждена без сигнала устаревания фрагмента.",
        ),
        fragments=(_fragment(),),
    )
    assert report.packets == ()
    assert engine.release_ready(report) is True


def test_missing_fragment_is_not_reconstructed_or_guessed() -> None:
    engine = SafeFragmentRedraftingEngine()
    report = engine.prepare(
        dependency_report=_report(
            stale=True,
            urgency=DoctrineImpactUrgency.CRITICAL,
            reason="Фрагмент зависит от правила, которое подтверждённо заменено/преодолено.",
        ),
        fragments=(),
    )
    assert report.packets == ()
