from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from jafar.telegram_runtime import TelegramBotHttpClient, TelegramRuntime


def test_telegram_runtime_defaults_to_dry_run() -> None:
    runtime = TelegramRuntime("123456:abcdefghijklmnopqrstuvwxyz")
    assert runtime.dry_run is True


def test_bot_client_rejects_empty_token() -> None:
    with pytest.raises(ValueError, match="telegram_bot_token_required"):
        TelegramBotHttpClient("   ")


def test_transport_exception_does_not_expose_token(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "123456:super-secret-telegram-token"

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **_kwargs):
            request = httpx.Request("POST", url)
            raise httpx.ConnectError("network failed", request=request)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: _Client())
    client = TelegramBotHttpClient(token)

    with pytest.raises(RuntimeError) as captured:
        asyncio.run(client.send_message(chat_id="1", text="confidential legal text"))

    assert token not in str(captured.value)
    assert "confidential legal text" not in str(captured.value)
    assert str(captured.value) == "Telegram sendMessage transport failed"


def test_non_success_http_status_is_secret_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "123456:super-secret-telegram-token"

    class _Response:
        status_code = 401

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, **_kwargs):
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: _Client())
    client = TelegramBotHttpClient(token)

    with pytest.raises(RuntimeError) as captured:
        asyncio.run(client.send_message(chat_id="1", text="private"))

    assert str(captured.value) == "Telegram sendMessage HTTP 401"
    assert token not in str(captured.value)


def test_send_poll_serializes_bot_api_10_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _Response:
        status_code = 200

        @staticmethod
        def json():
            return {
                "ok": True,
                "result": {
                    "message_id": 77,
                    "poll": {"id": "poll-77", "question": "Q", "options": []},
                },
            }

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: _Client())
    client = TelegramBotHttpClient("123456:super-secret-telegram-token")
    result = asyncio.run(
        client.send_poll(
            chat_id="-1001",
            poll={
                "question": "Q",
                "options": ["A", "B", "C"],
                "is_anonymous": False,
                "allows_multiple_answers": True,
                "type": "quiz",
                "correct_option_ids": [0, 2],
                "explanation": "Why",
                "open_period": 3600,
                "close_date": None,
            },
        )
    )

    assert result["message_id"] == 77
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    data = kwargs["data"]
    assert isinstance(data, dict)
    assert json.loads(data["options"]) == [
        {"text": "A"},
        {"text": "B"},
        {"text": "C"},
    ]
    assert json.loads(data["correct_option_ids"]) == [0, 2]
    assert "correct_option_id" not in data
    assert data["allows_multiple_answers"] == "true"
    assert data["open_period"] == "3600"
