from __future__ import annotations

import pytest

from jafar.telegram_mcp import _allowed_chat_ids, _require_allowed_chat


def test_allowed_chat_ids_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "123, 456,123")
    assert _allowed_chat_ids() == {"123", "456"}


def test_require_allowed_chat_rejects_unknown_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "123")
    with pytest.raises(PermissionError):
        _require_allowed_chat(999)


def test_require_allowed_chat_fails_closed_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_ALLOWED_CHAT_IDS", raising=False)
    with pytest.raises(RuntimeError):
        _require_allowed_chat(123)
