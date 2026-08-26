from __future__ import annotations

from datetime import UTC, date, datetime

from jafar.command_runtime import JafarCommandRuntime
from jafar.domains import MatterType
from jafar.legal_models import Deadline, Matter
from jafar.main import _resolve_command
from jafar.matters import MatterStore


def _store() -> MatterStore:
    store = MatterStore()
    now = datetime.now(UTC)
    store.create(
        Matter(
            id="matter-pavlik",
            title="Павлик В.А.",
            matter_type=MatterType.CRIMINAL,
            client_name="Павлик В.А.",
            opposing_party=None,
            court_or_authority="Следственный орган",
            case_number="12604008104000012",
            deadlines=[
                Deadline(
                    title="Подготовить процессуальный ответ",
                    due_date=date(2026, 8, 30),
                    source_text="Срок ответа до 30.08.2026",
                    confidence=0.9,
                )
            ],
            created_at=now,
            updated_at=now,
        )
    )
    store.add_event(
        "matter-pavlik",
        "Получен новый процессуальный документ",
        now,
        description="Документ требует проверки защиты.",
        source_document="procedural-note.txt",
    )
    return store


def test_attention_summary_surfaces_active_deadlines_without_approval():
    runtime = JafarCommandRuntime(_store())

    result = runtime.execute("attention_summary")

    assert result.approval_required is False
    assert result.data["attention_count"] == 1
    assert result.data["deadlines"][0]["matter_id"] == "matter-pavlik"
    assert result.data["deadlines"][0]["due_date"] == "2026-08-30"


def test_matter_update_finds_case_by_name_and_returns_latest_event():
    runtime = JafarCommandRuntime(_store())

    result = runtime.execute("matter_update", args={"query": "павлик"})

    assert result.approval_required is False
    assert result.data["matter"]["case_number"] == "12604008104000012"
    assert result.data["latest_event"]["title"] == "Получен новый процессуальный документ"
    assert result.data["deadlines"][0]["due_date"] == "2026-08-30"


def test_natural_language_router_covers_first_four_beta_commands():
    assert _resolve_command("Джафар, что требует моего внимания?")[0] == "attention_summary"

    intent, args = _resolve_command("Что нового по делу Павлик?")
    assert intent == "matter_update"
    assert args == {"query": "павлик"}

    assert _resolve_command("Разбери последнее юридическое письмо")[0] == "latest_legal_email"
    assert _resolve_command("Подготовь ответ")[0] == "prepare_reply"
