from jafar.case_action_planner import CaseActionPlanner


def test_planner_creates_approval_gated_actions():
    actions = CaseActionPlanner().plan(
        findings=[{"statement": "Вывод требует проверки", "basis": ["e1"], "requires_human_review": True}],
        deadlines=[{"title": "Срок", "due_at": "2026-08-25T00:00:00+00:00"}],
        contradictions=[{"left": "10 августа", "right": "12 августа", "evidence_ids": ["e1", "e2"], "severity": "high"}],
        gaps=[{"description": "Нет первичного документа", "expected_evidence": ["document"], "severity": "medium"}],
    )
    assert len(actions) == 4
    assert all(action.requires_approval for action in actions)
    assert any(action.priority == "critical" for action in actions)
