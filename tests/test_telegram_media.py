from __future__ import annotations

import asyncio

import pytest

from jafar import telegram_mcp
from jafar.config import settings


def setup(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "telegram_scheduler_db_path", str(tmp_path / "media.sqlite3"))


def test_content_plan_news_and_replacement(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path)
    plan = asyncio.run(telegram_mcp.telegram_content_plan_create("2026-09-01", ["допрос"], 7))
    assert len(plan["items"]) == 7
    updated = asyncio.run(telegram_mcp.telegram_content_plan_replace_item(plan["id"], 1, "Срочная новость"))
    assert updated["items"][0]["state"] == "breaking_news_replacement"
    news = asyncio.run(telegram_mcp.telegram_news_ingest("https://example.test/a", "Источник", "Новость", verified=True, relevance=.9))
    assert news["verified"] is True
    assert asyncio.run(telegram_mcp.telegram_news_suggest_post("Новость", .9, True))["recommendation"] == "breaking_news"


def test_case_redaction_comment_and_safe_generation(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path)
    case = asyncio.run(telegram_mcp.telegram_case_to_post("Клиент test@example.com, дело А40-12345/2026"))
    assert "test@example.com" not in case["body"]
    assert case["requires_approval"] is True
    comment = asyncio.run(telegram_mcp.telegram_comment_classify("Что делать, если меня задержали?"))
    assert comment["classification"] == "sensitive" and comment["requires_approval"]
    post = asyncio.run(telegram_mcp.telegram_generate_post("Ошибки допроса"))
    assert post["requires_approval"] and post["mode"] == "APPROVE"


def test_image_series_validation_and_no_fake_analytics(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path)
    image = asyncio.run(telegram_mcp.telegram_image_brief("допрос"))
    assert image["status"] == "requested" and image["provider"] is None
    with pytest.raises(ValueError):
        asyncio.run(telegram_mcp.telegram_image_brief("допрос", "16:9"))
    series = asyncio.run(telegram_mcp.telegram_series_create("Ошибки", 2, ["первая", "вторая"]))
    assert len(series["parts"]) == 2
    assert "basis" in asyncio.run(telegram_mcp.telegram_content_recommend_next())
