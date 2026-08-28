from jafar.attack_surface import AttackSeverity, AttackSurfaceItem, AttackSurfaceReport
from jafar.defense_action_planner import DefenseActionPlanner, DefenseActionType


def item(*, score: int, reasons: tuple[str, ...], defense: bool = False) -> AttackSurfaceItem:
    prosecution_source = {
        "evidence_id": "doc:1:page:8:chunk:1",
        "document_name": "Постановление.pdf",
        "page": 8,
        "chunk_index": 1,
        "actor": "следователь",
    }
    defense_sources = (
        {
            "evidence_id": "doc:2:page:14:chunk:3",
            "document_name": "Допрос.pdf",
            "page": 14,
            "chunk_index": 3,
            "actor": "свидетель",
        },
    ) if defense else ()
    severity = AttackSeverity.CRITICAL if score >= 80 else AttackSeverity.HIGH
    return AttackSurfaceItem(
        issue_id="theory:claim-1",
        topic="cash_transfer",
        statement="Деньги переданы",
        score=score,
        severity=severity,
        reasons=reasons,
        prosecution_sources=(prosecution_source,),
        defense_sources=defense_sources,
        recommended_focus=(),
    )


def test_high_priority_contradiction_creates_source_comparison_and_motion_draft() -> None:
    report = AttackSurfaceReport(
        items=(
            item(
                score=90,
                reasons=("Тезис уже связан с поддержанным источниками противоречием.",),
                defense=True,
            ),
        ),
        highest_priority_issue_ids=("theory:claim-1",),
        requires_human_review=True,
    )

    plan = DefenseActionPlanner().build(report)
    kinds = {action.action_type for action in plan.actions}
    assert DefenseActionType.COMPARE_CONTRADICTION in kinds
    assert DefenseActionType.WITNESS_PREP in kinds
    assert DefenseActionType.MOTION_DRAFT in kinds
    assert all(action.requires_lawyer_approval for action in plan.actions)


def test_timeline_signal_creates_timeline_check() -> None:
    report = AttackSurfaceReport(
        items=(
            item(
                score=70,
                reasons=("Тезис связан с нерешённым временным или иным review-сигналом.",),
            ),
        ),
        highest_priority_issue_ids=("theory:claim-1",),
        requires_human_review=True,
    )
    plan = DefenseActionPlanner().build(report)
    assert DefenseActionType.TIMELINE_CHECK in {action.action_type for action in plan.actions}


def test_single_source_creates_document_request_task() -> None:
    report = AttackSurfaceReport(
        items=(
            item(
                score=65,
                reasons=("Обвинительный тезис опирается на единственный конкретный источник.",),
            ),
        ),
        highest_priority_issue_ids=("theory:claim-1",),
        requires_human_review=True,
    )
    plan = DefenseActionPlanner().build(report)
    assert DefenseActionType.DOCUMENT_REQUEST in {action.action_type for action in plan.actions}


def test_snapshot_never_contains_execution_authority() -> None:
    report = AttackSurfaceReport(
        items=(item(score=80, reasons=("Нет подтверждения из нескольких независимых документов.",)),),
        highest_priority_issue_ids=("theory:claim-1",),
        requires_human_review=True,
    )
    snapshot = DefenseActionPlanner().snapshot(DefenseActionPlanner().build(report))
    text = repr(snapshot).casefold()
    assert snapshot["requires_lawyer_approval"] is True
    assert "execute" not in text
    assert "send" not in text
    assert "filed" not in text
    assert "submitted" not in text
