from __future__ import annotations

import base64

import pytest

from jafar.config import settings
from jafar.telegram_mcp import _allowed_chat_ids, _decode_photo_base64, _require_allowed_chat


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
