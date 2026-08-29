from __future__ import annotations

import asyncio
from datetime import timedelta
from itertools import pairwise

import pytest

from jafar import telegram_mcp
from jafar.config import settings
from jafar.telegram_editorial import EditorialStore, redact_transcript, safety_check
from jafar.telegram_publishing import PublishResult
from jafar.telegram_scheduler import TelegramScheduler, utc_now


def setup_editorial(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "telegram_scheduler_db_path", str(tmp_path / "editorial.sqlite3"))
    monkeypatch.setattr(settings, "telegram_allowed_chat_ids", "-1001")
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_editorial_mode", "APPROVE")


def test_default_approval_mode_and_high_risk_auto_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    setup_editorial(monkeypatch, tmp_path)
    draft = asyncio.run(
        telegram_mcp.telegram_editorial_generate_draft(
            topic="тактика", body="Контакт test@example.com"
        )
    )
    assert draft["mode"] == "APPROVE" and draft["state"] == "approval_required"
    auto = asyncio.run(
        telegram_mcp.telegram_editorial_generate_draft(
            topic="тактика", body="Паспорт клиента", mode="AUTO"
        )
    )
    assert auto["state"] == "approval_required"
    assert auto["safety"]["severity"] == "high"


def test_plan_is_persistent_non_repeating_and_supports_series(tmp_path) -> None:
    store = EditorialStore(tmp_path / "editorial.sqlite3")
    items = store.create_plan(
        week_start=utc_now().date(),
        topics=["тема"],
        rubrics=["A", "B"],
        windows=["09:00"],
        series_length=5,
    )
    assert len(items) == 5
    assert all(a.rubric != b.rubric for a, b in pairwise(items))
    assert len({item.series_id for item in items}) == 1
    assert len(EditorialStore(tmp_path / "editorial.sqlite3").list_items()) == 5


def test_safety_and_transcript_redaction() -> None:
    result = safety_check("Позвоните +7 999 123-45-67; тайна следствия")
    assert result["severity"] == "high"
    assert "test@example.com" not in redact_transcript("Эээ test@example.com, дело А40-12345/2026")
    assert "[redacted case number]" in redact_transcript("дело А40-12345/2026")


def test_approval_schedule_and_delivery_link(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    setup_editorial(monkeypatch, tmp_path)
    planned = asyncio.run(
        telegram_mcp.telegram_editorial_plan_week(
            utc_now().date().isoformat(),
            ["Тема"],
            rubrics=["Практика"],
            publishing_windows=["09:00"],
        )
    )["items"][0]
    draft = asyncio.run(
        telegram_mcp.telegram_editorial_generate_draft(
            item_id=planned["id"], body="Безопасный текст"
        )
    )
    with pytest.raises(PermissionError):
        asyncio.run(
            telegram_mcp.telegram_editorial_schedule_approved(
                draft["id"], "-1001", scheduled_for=(utc_now() + timedelta(minutes=1)).isoformat()
            )
        )
    asyncio.run(telegram_mcp.telegram_editorial_approve(draft["id"]))
    scheduled = asyncio.run(
        telegram_mcp.telegram_editorial_schedule_approved(
            draft["id"], "-1001", scheduled_for=(utc_now() + timedelta(minutes=1)).isoformat()
        )
    )
    assert scheduled["status"] == "pending"

    class Publisher:
        async def publish(self, **_: object) -> PublishResult:
            return PublishResult("text", [77])

    monkeypatch.setattr(telegram_mcp, "_publisher", lambda: Publisher())
    asyncio.run(
        TelegramScheduler(telegram_mcp._store(), telegram_mcp._deliver).run_due(
            utc_now() + timedelta(minutes=2)
        )
    )
    assert telegram_mcp._editorial().get_draft(draft["id"])["message_id"] == 77


def test_poll_followup_analytics_and_evergreen(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    setup_editorial(monkeypatch, tmp_path)
    draft = asyncio.run(
        telegram_mcp.telegram_editorial_generate_draft(topic="Тема", body="Безопасный текст")
    )
    proposal = asyncio.run(telegram_mcp.telegram_editorial_suggest_poll(draft["id"]))
    assert proposal["requires_approval"] is True and 2 <= len(proposal["options"]) <= 5
    assert (
        asyncio.run(telegram_mcp.telegram_editorial_mark_evergreen(draft["id"]))["evergreen"]
        is True
    )
    assert asyncio.run(telegram_mcp.telegram_editorial_performance())["items"] == []
    assert "ranked_rubrics" in asyncio.run(telegram_mcp.telegram_editorial_best_topics())
