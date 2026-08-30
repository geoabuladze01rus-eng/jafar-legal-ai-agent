from jafar.attack_surface import (
    AttackSeverity,
    AttackSignalKind,
    AttackSurfaceItem,
    AttackSurfaceReport,
)
from jafar.case_theory import CaseTheoryIssue, CaseTheoryReport, TheoryStatus
from jafar.court_outline import CourtOutlineGenerator, LegalAuthorityRef, OutlineKind
from jafar.hearing_preparation import HearingPreparationPlan, PreparationMode, PreparationStep


def make_theory(status: TheoryStatus = TheoryStatus.CONTRADICTED) -> CaseTheoryReport:
    issue = CaseTheoryIssue(
        issue_id="theory:claim-1",
        topic="money_transfer",
        statement="Денежные средства были переданы.",
        position="prosecution",
        status=status,
        claim_ids=("claim-1",),
        evidence_ids=("e1",),
        source_refs=(
            {
                "evidence_id": "e1",
                "document_name": "protocol.pdf",
                "document_fingerprint": "fp-protocol",
                "page": 8,
                "chunk_index": 1,
            },
        ),
        reasons=("Есть противоречие.",),
    )
    return CaseTheoryReport(
        issues=(issue,),
        supported_count=0,
        contradicted_count=1 if status == TheoryStatus.CONTRADICTED else 0,
        unsupported_count=1 if status == TheoryStatus.UNSUPPORTED else 0,
        review_required_count=1 if status == TheoryStatus.REVIEW_REQUIRED else 0,
        requires_human_review=True,
    )


def make_attack() -> AttackSurfaceReport:
    item = AttackSurfaceItem(
        issue_id="theory:claim-1",
        topic="money_transfer",
        statement="Денежные средства были переданы.",
        score=85,
        severity=AttackSeverity.CRITICAL,
        signals=(
            AttackSignalKind.CONTRADICTED,
            AttackSignalKind.SINGLE_SOURCE,
            AttackSignalKind.DEFENSE_COUNTERTHESIS,
        ),
        reasons=("Тезис зависит от одного источника.",),
        prosecution_sources=(
            {
                "evidence_id": "e1",
                "document_name": "protocol.pdf",
                "document_fingerprint": "fp-protocol",
                "page": 8,
            },
        ),
        defense_sources=(
            {
                "evidence_id": "e2",
                "document_name": "interview.pdf",
                "document_fingerprint": "fp-interview",
                "page": 14,
            },
        ),
        recommended_focus=("Сопоставить версии.",),
    )
    return AttackSurfaceReport(
        items=(item,),
        highest_priority_issue_ids=(item.issue_id,),
        requires_human_review=True,
    )


def make_hearing() -> HearingPreparationPlan:
    step = PreparationStep(
        step_id="prep:theory:claim-1:1",
        issue_id="theory:claim-1",
        topic="money_transfer",
        sequence=1,
        objective="Проверить противоречие.",
        primary_questions=("Из какого источника вам это известно?",),
        fallback_questions=("Что вы наблюдали лично?",),
        documents_to_present=(
            {"evidence_id": "e1", "document_name": "protocol.pdf", "page": 8},
        ),
        contradiction_sequence=("Сначала получить самостоятельную версию.",),
        caution="Тактику определяет адвокат.",
    )
    return HearingPreparationPlan(
        mode=PreparationMode.HEARING,
        steps=(step,),
        document_index=step.documents_to_present,
    )


def test_outline_preserves_source_refs_and_questions() -> None:
    outline = CourtOutlineGenerator().build(
        theory=make_theory(),
        attack_surface=make_attack(),
        hearing=make_hearing(),
    )
    section = outline.sections[0]
    assert section.evidence_refs[0]["page"] == 8
    assert section.contradiction_points
    assert "Из какого источника" in section.hearing_questions[0]
    assert section.requires_lawyer_approval is True


def test_outline_does_not_invent_authorities_or_relief() -> None:
    outline = CourtOutlineGenerator().build(
        theory=make_theory(),
        attack_surface=make_attack(),
        hearing=make_hearing(),
        kind=OutlineKind.MOTION,
    )
    section = outline.sections[0]
    assert section.authorities == ()
    assert section.requested_relief == ()
    snapshot = CourtOutlineGenerator().snapshot(outline)
    text = repr(snapshot).casefold()
    assert "ст. 75" not in text
    assert "удовлетворить" not in text
    assert snapshot["requires_lawyer_approval"] is True


def test_unverified_authority_is_flagged_for_source_verification() -> None:
    authority = LegalAuthorityRef(
        citation="УПК РФ, статья X",
        proposition="Проверить применимость нормы.",
        verified=False,
    )
    outline = CourtOutlineGenerator().build(
        theory=make_theory(),
        attack_surface=make_attack(),
        hearing=make_hearing(),
        authorities_by_topic={"money_transfer": (authority,)},
    )
    assert outline.requires_source_verification is True
    assert outline.unverified_authorities == ("УПК РФ, статья X",)


def test_verified_authority_and_relief_are_only_caller_supplied() -> None:
    authority = LegalAuthorityRef(
        citation="Проверенная норма",
        proposition="Проверенная правовая позиция.",
        verified=True,
        source_url="https://example.test/law",
    )
    outline = CourtOutlineGenerator().build(
        theory=make_theory(TheoryStatus.SUPPORTED),
        attack_surface=make_attack(),
        hearing=make_hearing(),
        authorities_by_topic={"money_transfer": (authority,)},
        relief_by_topic={
            "money_transfer": ("Просительная формулировка, заданная адвокатом.",)
        },
    )
    section = outline.sections[0]
    assert section.authorities == (authority,)
    assert section.requested_relief == (
        "Просительная формулировка, заданная адвокатом.",
    )
    assert outline.requires_source_verification is False
