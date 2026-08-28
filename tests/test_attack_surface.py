from jafar.attack_surface import (
    AttackSeverity,
    AttackSignalKind,
    ProsecutionAttackSurfaceEngine,
)
from jafar.case_theory import TheoryStatus
from jafar.theory_views import DualTheoryReport, TheorySide, TheoryViewItem


def item(
    issue_id: str,
    topic: str,
    side: TheorySide,
    status: TheoryStatus,
    *,
    source: str,
    actor: str = "actor",
) -> TheoryViewItem:
    return TheoryViewItem(
        issue_id=issue_id,
        topic=topic,
        statement=issue_id,
        side=side,
        status=status,
        evidence_ids=(source,),
        source_refs=(
            {
                "evidence_id": source,
                "document_name": f"{source}.pdf",
                "document_fingerprint": f"fp:{source}",
                "page": 1,
                "chunk_index": 0,
                "actor": actor,
                "event_id": None,
                "excerpt": issue_id,
            },
        ),
        reasons=(),
    )


def test_single_source_contradicted_thesis_with_defense_counterpoint_ranks_critical() -> None:
    prosecution = item(
        "p1",
        "payment",
        TheorySide.PROSECUTION,
        TheoryStatus.CONTRADICTED,
        source="p-src",
    )
    defense = item(
        "d1",
        "payment",
        TheorySide.DEFENSE,
        TheoryStatus.SUPPORTED,
        source="d-src",
        actor="witness",
    )
    report = DualTheoryReport(
        prosecution=(prosecution,),
        defense=(defense,),
        neutral=(),
        conflict_points=(),
        requires_human_review=True,
    )

    result = ProsecutionAttackSurfaceEngine().build(report)
    attack = result.items[0]

    assert attack.issue_id == "p1"
    assert attack.score == 100
    assert attack.severity == AttackSeverity.CRITICAL
    assert AttackSignalKind.CONTRADICTED in attack.signals
    assert AttackSignalKind.SINGLE_SOURCE in attack.signals
    assert AttackSignalKind.DEFENSE_COUNTERTHESIS in attack.signals
    assert attack.defense_sources[0]["evidence_id"] == "d-src"
    assert "p1" in result.highest_priority_issue_ids


def test_supported_thesis_with_multiple_independent_fingerprints_has_lower_priority() -> None:
    prosecution = TheoryViewItem(
        issue_id="p2",
        topic="identity",
        statement="identity established",
        side=TheorySide.PROSECUTION,
        status=TheoryStatus.SUPPORTED,
        evidence_ids=("s1", "s2"),
        source_refs=(
            {
                "evidence_id": "s1",
                "document_name": "a.pdf",
                "document_fingerprint": "fp-a",
                "page": 1,
                "chunk_index": 0,
                "actor": "w1",
                "event_id": None,
                "excerpt": "a",
            },
            {
                "evidence_id": "s2",
                "document_name": "b.pdf",
                "document_fingerprint": "fp-b",
                "page": 2,
                "chunk_index": 0,
                "actor": "w2",
                "event_id": None,
                "excerpt": "b",
            },
        ),
        reasons=(),
    )
    result = ProsecutionAttackSurfaceEngine().build(
        DualTheoryReport(
            prosecution=(prosecution,),
            defense=(),
            neutral=(),
            conflict_points=(),
            requires_human_review=False,
        )
    )

    assert result.items[0].score == 0
    assert result.items[0].severity == AttackSeverity.LOW
    assert result.items[0].signals == ()


def test_two_file_names_with_same_fingerprint_are_not_treated_as_independent() -> None:
    prosecution = TheoryViewItem(
        issue_id="p-fp",
        topic="identity",
        statement="identity established",
        side=TheorySide.PROSECUTION,
        status=TheoryStatus.SUPPORTED,
        evidence_ids=("s1", "s2"),
        source_refs=(
            {
                "evidence_id": "s1",
                "document_name": "copy-a.pdf",
                "document_fingerprint": "same-fp",
                "page": 1,
                "actor": "w1",
            },
            {
                "evidence_id": "s2",
                "document_name": "renamed-copy.pdf",
                "document_fingerprint": "same-fp",
                "page": 2,
                "actor": "w2",
            },
        ),
        reasons=(),
    )

    result = ProsecutionAttackSurfaceEngine().build(
        DualTheoryReport(
            prosecution=(prosecution,),
            defense=(),
            neutral=(),
            conflict_points=(),
            requires_human_review=False,
        )
    )

    assert AttackSignalKind.SINGLE_DOCUMENT_FINGERPRINT in result.items[0].signals
    assert result.items[0].score == 10


def test_unsupported_prosecution_thesis_is_high_priority_even_without_defense_counterpoint() -> None:
    prosecution = TheoryViewItem(
        issue_id="p3",
        topic="intent",
        statement="intent existed",
        side=TheorySide.PROSECUTION,
        status=TheoryStatus.UNSUPPORTED,
        evidence_ids=(),
        source_refs=(),
        reasons=(),
    )
    result = ProsecutionAttackSurfaceEngine().build(
        DualTheoryReport(
            prosecution=(prosecution,),
            defense=(),
            neutral=(),
            conflict_points=(),
            requires_human_review=True,
        )
    )

    assert result.items[0].score >= 60
    assert result.items[0].severity in {AttackSeverity.HIGH, AttackSeverity.CRITICAL}
    assert AttackSignalKind.UNSUPPORTED in result.items[0].signals
    assert result.highest_priority_issue_ids == ("p3",)


def test_ranking_orders_more_vulnerable_thesis_first() -> None:
    weak = item(
        "weak",
        "payment",
        TheorySide.PROSECUTION,
        TheoryStatus.CONTRADICTED,
        source="weak-src",
    )
    strong = TheoryViewItem(
        issue_id="strong",
        topic="identity",
        statement="identity established",
        side=TheorySide.PROSECUTION,
        status=TheoryStatus.SUPPORTED,
        evidence_ids=("s1", "s2"),
        source_refs=(
            {
                "evidence_id": "s1",
                "document_name": "a.pdf",
                "document_fingerprint": "fp-a",
                "page": 1,
                "actor": "w1",
            },
            {
                "evidence_id": "s2",
                "document_name": "b.pdf",
                "document_fingerprint": "fp-b",
                "page": 2,
                "actor": "w2",
            },
        ),
        reasons=(),
    )
    result = ProsecutionAttackSurfaceEngine().build(
        DualTheoryReport(
            prosecution=(strong, weak),
            defense=(),
            neutral=(),
            conflict_points=(),
            requires_human_review=True,
        )
    )

    assert [entry.issue_id for entry in result.items] == ["weak", "strong"]
