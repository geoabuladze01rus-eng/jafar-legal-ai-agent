from __future__ import annotations

import base64

import pytest

from jafar.config import settings
from jafar.telegram_mcp import (
    _allowed_chat_ids,
    _decode_photo_base64,
    _key,
    _require_allowed_chat,
    validate_mcp_transport_security,
)


def test_allowed_chat_ids_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "telegram_allowed_chat_ids", "123, 456,123")
    assert _allowed_chat_ids() == {"123", "456"}


def test_require_allowed_chat_rejects_unknown_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "telegram_allowed_chat_ids", "123")
    with pytest.raises(PermissionError):
        _require_allowed_chat(999)


def test_require_allowed_chat_fails_closed_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "telegram_allowed_chat_ids", "")
    with pytest.raises(RuntimeError):
        _require_allowed_chat(123)


def test_decode_photo_base64_accepts_plain_base64() -> None:
    payload = b"fake-image-bytes"
    encoded = base64.b64encode(payload).decode("ascii")
    assert _decode_photo_base64(encoded) == payload


def test_decode_photo_base64_accepts_data_url() -> None:
    payload = b"fake-image-bytes"
    encoded = base64.b64encode(payload).decode("ascii")
    assert _decode_photo_base64(f"data:image/png;base64,{encoded}") == payload


def test_decode_photo_base64_rejects_invalid_input() -> None:
    with pytest.raises(ValueError, match="not valid base64"):
        _decode_photo_base64("%%%not-base64%%%")


def test_decode_photo_base64_rejects_empty_file() -> None:
    with pytest.raises(ValueError, match="empty file"):
        _decode_photo_base64("")


def test_streamable_http_requires_strong_bearer_even_on_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "jafar_mcp_auth_token", None)
    monkeypatch.setattr(settings, "jafar_mcp_public_url", "https://mcp.example/mcp")

    with pytest.raises(RuntimeError, match="at least 32 characters"):
        validate_mcp_transport_security(transport="streamable-http", host="127.0.0.1")


def test_streamable_http_requires_https_public_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jafar_mcp_auth_token", "x" * 40)
    monkeypatch.setattr(settings, "jafar_mcp_public_url", "http://mcp.example/mcp")

    with pytest.raises(RuntimeError, match="HTTPS"):
        validate_mcp_transport_security(transport="streamable-http", host="127.0.0.1")


def test_streamable_http_refuses_direct_non_loopback_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "jafar_mcp_auth_token", "x" * 40)
    monkeypatch.setattr(settings, "jafar_mcp_public_url", "https://mcp.example/mcp")

    with pytest.raises(RuntimeError, match="loopback"):
        validate_mcp_transport_security(transport="streamable-http", host="0.0.0.0")


def test_streamable_http_accepts_hardened_proxy_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "jafar_mcp_auth_token", "x" * 40)
    monkeypatch.setattr(settings, "jafar_mcp_public_url", "https://mcp.example/mcp")

    assert validate_mcp_transport_security(
        transport="streamable-http", host="127.0.0.1"
    ) == ("x" * 40, "https://mcp.example/mcp")


def test_stdio_does_not_require_remote_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jafar_mcp_auth_token", None)
    monkeypatch.setattr(settings, "jafar_mcp_public_url", None)

    assert validate_mcp_transport_security(transport="stdio") is None


def test_idempotency_key_rejects_whitespace_only_value() -> None:
    with pytest.raises(ValueError, match="non-whitespace"):
        _key("post", "123", {"text": "hello"}, "2026-08-30T09:00:00+00:00", "   ")
