from jafar.defense_action_planner import DefenseAction, DefenseActionPlan, DefenseActionType
from jafar.hearing_preparation import HearingPreparationEngine, PreparationMode


def _action(action_type: DefenseActionType, priority: int = 90) -> DefenseAction:
    return DefenseAction(
        action_id=f"action:issue-1:{action_type.value}",
        issue_id="issue-1",
        topic="payment_transfer",
        action_type=action_type,
        priority=priority,
        title="test",
        rationale="test",
        source_refs=(
            {
                "evidence_id": "doc:a:page:8:chunk:1",
                "document_name": "Постановление.pdf",
                "page": 8,
                "chunk_index": 1,
                "actor": "Следователь",
                "excerpt": "Передача денежных средств установлена.",
            },
            {
                "evidence_id": "doc:b:page:14:chunk:2",
                "document_name": "Допрос.pdf",
                "page": 14,
                "chunk_index": 2,
                "actor": "Свидетель",
                "excerpt": "Денежные средства не передавались.",
            },
        ),
    )


def test_hearing_plan_orders_contradiction_before_document_confrontation() -> None:
    plan = DefenseActionPlan(
        actions=(
            _action(DefenseActionType.COMPARE_CONTRADICTION),
            _action(DefenseActionType.WITNESS_PREP, 85),
        ),
        highest_priority_action_ids=("action:issue-1:compare_contradiction",),
    )
    result = HearingPreparationEngine().build(plan, mode=PreparationMode.HEARING)
    step = result.steps[0]
    assert step.sequence == 1
    assert "самостоятельное изложение" in step.contradiction_sequence[0]
    assert any("Постановление.pdf, стр. 8" in item for item in step.contradiction_sequence)
    assert len(step.documents_to_present) == 2
    assert step.requires_lawyer_approval is True


def test_interrogation_mode_adds_source_of_knowledge_questions() -> None:
    plan = DefenseActionPlan(
        actions=(_action(DefenseActionType.WITNESS_PREP),),
        highest_priority_action_ids=(),
    )
    result = HearingPreparationEngine().build(plan, mode=PreparationMode.INTERROGATION)
    questions = result.steps[0].primary_questions
    assert any("конкретно источника" in item for item in questions)
    assert any("лично" in item for item in result.steps[0].fallback_questions)


def test_timeline_action_generates_time_questions() -> None:
    plan = DefenseActionPlan(
        actions=(_action(DefenseActionType.TIMELINE_CHECK),),
        highest_priority_action_ids=(),
    )
    result = HearingPreparationEngine().build(plan)
    step = result.steps[0]
    assert any("дату и время" in item for item in step.primary_questions)
    assert "хронолог" in step.objective.casefold()


def test_snapshot_has_no_execution_authority() -> None:
    plan = DefenseActionPlan(
        actions=(_action(DefenseActionType.MOTION_DRAFT),),
        highest_priority_action_ids=(),
    )
    snapshot = HearingPreparationEngine().snapshot(HearingPreparationEngine().build(plan))
    assert snapshot["requires_lawyer_approval"] is True
    text = repr(snapshot).casefold()
    for forbidden in ("execute", "submitted", "filed", "sent"):
        assert forbidden not in text
