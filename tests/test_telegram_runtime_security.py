from __future__ import annotations

import asyncio

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
