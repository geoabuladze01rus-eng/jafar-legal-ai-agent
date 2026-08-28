from datetime import datetime, timezone

from jafar.evidence_graph import CaseEvidenceGraph, EvidenceSource
from jafar.timeline_contradictions import TimelineAssertion, TimelineContradictionAnalyzer


def dt(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 8, day, hour, tzinfo=timezone.utc)


def source(evidence_id: str, document_name: str, page: int, actor: str) -> EvidenceSource:
    return EvidenceSource(
        evidence_id=evidence_id,
        document_name=document_name,
        document_fingerprint=evidence_id,
        excerpt=f"Источник {document_name}",
        page=page,
        actor=actor,
        metadata={"chunk_index": 1},
    )


def test_flags_conflicting_exact_dates_for_same_topic() -> None:
    graph = CaseEvidenceGraph()
    graph.add_source(source("e1", "Допрос 1", 4, "Свидетель"))
    graph.add_source(source("e2", "Допрос 2", 9, "Свидетель"))
    assertions = (
        TimelineAssertion(
            "a1",
            "встреча",
            dt(12),
            None,
            None,
            "Свидетель",
            ("e1",),
            "Встреча была 12 августа",
        ),
        TimelineAssertion(
            "a2",
            "встреча",
            dt(14),
            None,
            None,
            "Свидетель",
            ("e2",),
            "Встреча была 14 августа",
        ),
    )

    result = TimelineContradictionAnalyzer().analyze(graph, assertions)

    assert len(result) == 1
    assert result[0].kind == "conflicting_exact_dates"
    assert result[0].left_sources[0].page == 4
    assert result[0].right_sources[0].page == 9


def test_flags_disjoint_windows_for_same_event() -> None:
    graph = CaseEvidenceGraph()
    graph.add_source(source("e1", "Протокол", 3, "Следователь"))
    graph.add_source(source("e2", "Биллинг", 1, "Оператор"))
    assertions = (
        TimelineAssertion(
            "a1",
            "местонахождение",
            None,
            dt(10),
            dt(11),
            "Следователь",
            ("e1",),
            "Лицо было в Краснодаре",
        ),
        TimelineAssertion(
            "a2",
            "местонахождение",
            None,
            dt(13),
            dt(14),
            "Оператор",
            ("e2",),
            "Телефон зарегистрирован в Москве",
        ),
    )

    result = TimelineContradictionAnalyzer().analyze(graph, assertions)

    assert len(result) == 1
    assert result[0].kind == "disjoint_time_windows"


def test_flags_disjoint_windows_in_both_chronological_directions() -> None:
    graph = CaseEvidenceGraph()
    graph.add_source(source("e1", "Источник 1", 1, "A"))
    graph.add_source(source("e2", "Источник 2", 2, "B"))
    assertions = (
        TimelineAssertion("a1", "событие", None, dt(15), dt(16), "A", ("e1",), "Позднее окно"),
        TimelineAssertion("a2", "событие", None, dt(10), dt(11), "B", ("e2",), "Раннее окно"),
    )

    result = TimelineContradictionAnalyzer().analyze(graph, assertions)

    assert len(result) == 1
    assert result[0].kind == "disjoint_time_windows"


def test_flags_assertion_outside_its_own_allowed_window() -> None:
    graph = CaseEvidenceGraph()
    graph.add_source(source("e1", "Заключение", 7, "Эксперт"))
    assertions = (
        TimelineAssertion(
            "a1",
            "экспертиза",
            dt(9),
            dt(10),
            dt(12),
            "Эксперт",
            ("e1",),
            "Исследование проведено 9 августа",
        ),
    )

    result = TimelineContradictionAnalyzer().analyze(graph, assertions)

    assert len(result) == 1
    assert result[0].kind == "before_earliest"


def test_ignores_unreferenced_timeline_assertions() -> None:
    graph = CaseEvidenceGraph()
    assertions = (
        TimelineAssertion("a1", "обыск", dt(12), None, None, "Модель", (), "Обыск 12 августа"),
        TimelineAssertion("a2", "обыск", dt(14), None, None, "Модель", (), "Обыск 14 августа"),
    )

    assert TimelineContradictionAnalyzer().analyze(graph, assertions) == ()


def test_partial_invalid_evidence_set_does_not_support_timeline_signal() -> None:
    graph = CaseEvidenceGraph()
    graph.add_source(source("e1", "Допрос", 4, "Свидетель"))
    graph.add_source(source("e2", "Биллинг", 1, "Оператор"))
    assertions = (
        TimelineAssertion(
            "a1",
            "встреча",
            dt(12),
            None,
            None,
            "Свидетель",
            ("e1", "missing"),
            "Встреча была 12 августа",
        ),
        TimelineAssertion(
            "a2",
            "встреча",
            dt(14),
            None,
            None,
            "Оператор",
            ("e2",),
            "Встреча была 14 августа",
        ),
    )

    assert TimelineContradictionAnalyzer().analyze(graph, assertions) == ()


def test_snapshot_preserves_source_trace() -> None:
    graph = CaseEvidenceGraph()
    graph.add_source(source("e1", "Допрос", 12, "Свидетель"))
    graph.add_source(source("e2", "Постановление", 5, "Следователь"))
    assertions = (
        TimelineAssertion("a1", "передача", dt(12), None, None, "Свидетель", ("e1",), "Передача 12 августа"),
        TimelineAssertion("a2", "передача", dt(14), None, None, "Следователь", ("e2",), "Передача 14 августа"),
    )

    snapshot = TimelineContradictionAnalyzer().snapshot(graph, assertions)

    assert snapshot["requires_human_review"] is True
    item = snapshot["timeline_contradictions"][0]
    assert item["left_sources"][0]["document_name"] == "Допрос"
    assert item["right_sources"][0]["document_name"] == "Постановление"
