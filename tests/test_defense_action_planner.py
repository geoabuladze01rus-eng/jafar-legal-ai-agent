from jafar.attack_surface import (
    AttackSeverity,
    AttackSignalKind,
    AttackSurfaceItem,
    AttackSurfaceReport,
)
from jafar.defense_action_planner import DefenseActionPlanner, DefenseActionType


def item(
    *,
    score: int,
    signals: tuple[AttackSignalKind, ...],
    reasons: tuple[str, ...] = (),
    defense: bool = False,
) -> AttackSurfaceItem:
    prosecution_source = {
        "evidence_id": "doc:1:page:8:chunk:1",
        "document_name": "Постановление.pdf",
        "document_fingerprint": "fp-1",
        "page": 8,
        "chunk_index": 1,
        "actor": "следователь",
    }
    defense_sources = (
        {
            "evidence_id": "doc:2:page:14:chunk:3",
            "document_name": "Допрос.pdf",
            "document_fingerprint": "fp-2",
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
        signals=signals,
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
                signals=(AttackSignalKind.CONTRADICTED,),
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


def test_review_required_signal_creates_timeline_check_without_parsing_reason_text() -> None:
    report = AttackSurfaceReport(
        items=(
            item(
                score=70,
                signals=(AttackSignalKind.REVIEW_REQUIRED,),
                reasons=("Произвольный человекочитаемый текст без слова хронология.",),
            ),
        ),
        highest_priority_issue_ids=("theory:claim-1",),
        requires_human_review=True,
    )
    plan = DefenseActionPlanner().build(report)
    assert DefenseActionType.TIMELINE_CHECK in {action.action_type for action in plan.actions}


def test_single_source_signal_creates_document_request_task() -> None:
    report = AttackSurfaceReport(
        items=(
            item(
                score=65,
                signals=(AttackSignalKind.SINGLE_SOURCE,),
                reasons=("Текст причины может быть изменён без изменения поведения planner.",),
            ),
        ),
        highest_priority_issue_ids=("theory:claim-1",),
        requires_human_review=True,
    )
    plan = DefenseActionPlanner().build(report)
    assert DefenseActionType.DOCUMENT_REQUEST in {
        action.action_type for action in plan.actions
    }


def test_reason_prose_alone_does_not_trigger_control_flow() -> None:
    report = AttackSurfaceReport(
        items=(
            item(
                score=50,
                signals=(),
                reasons=(
                    "противоречие временное единственный источник нет подтверждения",
                ),
            ),
        ),
        highest_priority_issue_ids=(),
        requires_human_review=True,
    )

    plan = DefenseActionPlanner().build(report)
    kinds = {action.action_type for action in plan.actions}

    assert kinds == {DefenseActionType.VERIFY_SOURCE}


def test_snapshot_never_contains_execution_authority() -> None:
    report = AttackSurfaceReport(
        items=(
            item(
                score=80,
                signals=(AttackSignalKind.SINGLE_DOCUMENT_FINGERPRINT,),
            ),
        ),
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
