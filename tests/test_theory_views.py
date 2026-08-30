import pytest

from jafar.case_theory import CaseTheoryIssue, CaseTheoryReport, TheoryStatus
from jafar.theory_views import (
    ProsecutionDefenseTheoryView,
    TheorySide,
    TheorySideAssignment,
)


def issue(
    issue_id: str,
    topic: str,
    statement: str,
    position: str,
    status: TheoryStatus,
    evidence_id: str,
    document: str,
    page: int,
) -> CaseTheoryIssue:
    return CaseTheoryIssue(
        issue_id=issue_id,
        topic=topic,
        statement=statement,
        position=position,
        status=status,
        claim_ids=(issue_id.replace("theory:", ""),),
        evidence_ids=(evidence_id,),
        source_refs=(
            {
                "evidence_id": evidence_id,
                "document_name": document,
                "page": page,
                "chunk_index": 0,
                "actor": None,
                "event_id": None,
                "excerpt": statement,
            },
        ),
        reasons=(),
    )


def report(*issues: CaseTheoryIssue) -> CaseTheoryReport:
    return CaseTheoryReport(
        issues=issues,
        supported_count=sum(item.status == TheoryStatus.SUPPORTED for item in issues),
        contradicted_count=sum(item.status == TheoryStatus.CONTRADICTED for item in issues),
        unsupported_count=sum(item.status == TheoryStatus.UNSUPPORTED for item in issues),
        review_required_count=sum(item.status == TheoryStatus.REVIEW_REQUIRED for item in issues),
        requires_human_review=any(item.status != TheoryStatus.SUPPORTED for item in issues),
    )


def test_builds_parallel_views_only_from_explicit_assignments() -> None:
    engine = ProsecutionDefenseTheoryView()
    theory = report(
        issue(
            "theory:p1",
            "money_transfer",
            "Денежные средства были переданы.",
            "occurred",
            TheoryStatus.CONTRADICTED,
            "doc:p:page:8:chunk:1",
            "Постановление следователя.pdf",
            8,
        ),
        issue(
            "theory:d1",
            "money_transfer",
            "Передача денежных средств не происходила.",
            "did_not_occur",
            TheoryStatus.SUPPORTED,
            "doc:d:page:14:chunk:3",
            "Протокол допроса.pdf",
            14,
        ),
    )
    result = engine.build(
        theory,
        assignments=(
            TheorySideAssignment("theory:p1", TheorySide.PROSECUTION, "lawyer:chernov"),
            TheorySideAssignment("theory:d1", TheorySide.DEFENSE, "lawyer:chernov"),
        ),
    )

    assert len(result.prosecution) == 1
    assert len(result.defense) == 1
    assert result.prosecution[0].side == TheorySide.PROSECUTION
    assert result.defense[0].side == TheorySide.DEFENSE
    assert len(result.conflict_points) == 1
    conflict = result.conflict_points[0]
    assert conflict.topic == "money_transfer"
    assert conflict.defense_challenges_prosecution is True
    assert conflict.prosecution_sources[0]["page"] == 8
    assert conflict.defense_sources[0]["page"] == 14


def test_generic_positions_do_not_auto_assign_sides() -> None:
    theory = report(
        issue(
            "theory:p1",
            "presence",
            "Обвиняемый присутствовал.",
            "present",
            TheoryStatus.SUPPORTED,
            "e1",
            "Протокол.pdf",
            5,
        ),
        issue(
            "theory:d1",
            "presence",
            "Обвиняемый отсутствовал.",
            "absent",
            TheoryStatus.SUPPORTED,
            "e2",
            "Видеозапись.txt",
            1,
        ),
    )

    result = ProsecutionDefenseTheoryView().build(theory)

    assert not result.prosecution
    assert not result.defense
    assert {item.issue_id for item in result.neutral} == {"theory:p1", "theory:d1"}
    assert result.conflict_points == ()


def test_does_not_create_conflict_for_different_topics() -> None:
    theory = report(
        issue(
            "theory:p1",
            "intent",
            "Умысел имелся.",
            "guilt",
            TheoryStatus.SUPPORTED,
            "e1",
            "Обвинение.pdf",
            3,
        ),
        issue(
            "theory:d1",
            "alibi",
            "Лицо находилось в другом месте.",
            "defense",
            TheoryStatus.SUPPORTED,
            "e2",
            "Билет.pdf",
            1,
        ),
    )
    result = ProsecutionDefenseTheoryView().build(
        theory,
        assignments=(
            TheorySideAssignment("theory:p1", TheorySide.PROSECUTION),
            TheorySideAssignment("theory:d1", TheorySide.DEFENSE),
        ),
    )
    assert result.conflict_points == ()


def test_neutral_positions_stay_out_of_both_sides() -> None:
    result = ProsecutionDefenseTheoryView().build(
        report(
            issue(
                "theory:n1",
                "jurisdiction",
                "Подсудность требует проверки.",
                "uncertain",
                TheoryStatus.REVIEW_REQUIRED,
                "e1",
                "Справка.pdf",
                2,
            )
        )
    )
    assert not result.prosecution
    assert not result.defense
    assert len(result.neutral) == 1


def test_rejects_unknown_or_duplicate_assignments() -> None:
    theory = report(
        issue(
            "theory:n1",
            "jurisdiction",
            "Подсудность требует проверки.",
            "uncertain",
            TheoryStatus.REVIEW_REQUIRED,
            "e1",
            "Справка.pdf",
            2,
        )
    )
    engine = ProsecutionDefenseTheoryView()

    with pytest.raises(ValueError, match="Unknown theory issue_id"):
        engine.build(
            theory,
            assignments=(TheorySideAssignment("theory:missing", TheorySide.DEFENSE),),
        )

    with pytest.raises(ValueError, match="Duplicate"):
        engine.build(
            theory,
            assignments=(
                TheorySideAssignment("theory:n1", TheorySide.DEFENSE),
                TheorySideAssignment("theory:n1", TheorySide.PROSECUTION),
            ),
        )


def test_snapshot_preserves_both_source_trails_without_declaring_winner() -> None:
    view = ProsecutionDefenseTheoryView()
    theory = report(
        issue(
            "theory:p1",
            "presence",
            "Обвиняемый присутствовал.",
            "present",
            TheoryStatus.CONTRADICTED,
            "e1",
            "Протокол.pdf",
            5,
        ),
        issue(
            "theory:d1",
            "presence",
            "Обвиняемый отсутствовал.",
            "absent",
            TheoryStatus.SUPPORTED,
            "e2",
            "Видеозапись.txt",
            1,
        ),
    )
    built = view.build(
        theory,
        assignments=(
            TheorySideAssignment("theory:p1", TheorySide.PROSECUTION),
            TheorySideAssignment("theory:d1", TheorySide.DEFENSE),
        ),
    )
    snapshot = view.snapshot(built)
    assert snapshot["conflict_points"][0]["prosecution_sources"][0]["document_name"] == "Протокол.pdf"
    assert snapshot["conflict_points"][0]["defense_sources"][0]["document_name"] == "Видеозапись.txt"
    assert "winner" not in snapshot["conflict_points"][0]
    assert snapshot["requires_human_review"] is True
