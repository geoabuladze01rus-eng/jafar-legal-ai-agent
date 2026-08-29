from __future__ import annotations

import pytest

from jafar.config import Settings
from jafar.telegram_security import live_send_enabled, validate_telegram_settings


def _settings(**values) -> Settings:
    return Settings(_env_file=None, **values)


def test_default_telegram_configuration_is_non_sending() -> None:
    settings = _settings()
    validate_telegram_settings(settings)
    assert live_send_enabled(settings) is False


def test_live_send_requires_explicit_non_dry_run_mode() -> None:
    with pytest.raises(RuntimeError, match="conflicts"):
        validate_telegram_settings(
            _settings(
                telegram_bot_token="token",
                telegram_allowed_chat_ids="-1001",
                telegram_production_send=True,
                telegram_dry_run=True,
            )
        )


def test_live_send_requires_token_and_allowlist() -> None:
    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        validate_telegram_settings(
            _settings(
                telegram_production_send=True,
                telegram_dry_run=False,
                telegram_allowed_chat_ids="-1001",
            )
        )
    with pytest.raises(RuntimeError, match="ALLOWED_CHAT_IDS"):
        validate_telegram_settings(
            _settings(
                telegram_bot_token="token",
                telegram_production_send=True,
                telegram_dry_run=False,
            )
        )


def test_enabled_polling_and_scheduler_require_bot_token() -> None:
    with pytest.raises(RuntimeError, match="POLLING_ENABLED"):
        validate_telegram_settings(
            _settings(telegram_polling_enabled=True, telegram_allowed_chat_ids="-1001")
        )
    with pytest.raises(RuntimeError, match="SCHEDULER_ENABLED"):
        validate_telegram_settings(
            _settings(telegram_scheduler_enabled=True, telegram_allowed_chat_ids="-1001")
        )


def test_enabled_telegram_workers_require_allowlist_even_outside_production() -> None:
    with pytest.raises(RuntimeError, match="POLLING_ENABLED requires TELEGRAM_ALLOWED_CHAT_IDS"):
        validate_telegram_settings(
            _settings(
                telegram_bot_token="token",
                telegram_polling_enabled=True,
            )
        )
    with pytest.raises(RuntimeError, match="SCHEDULER_ENABLED requires TELEGRAM_ALLOWED_CHAT_IDS"):
        validate_telegram_settings(
            _settings(
                telegram_bot_token="token",
                telegram_scheduler_enabled=True,
            )
        )


def test_production_polling_requires_strong_pseudonym_secret() -> None:
    base = {
        "environment": "production",
        "telegram_bot_token": "token",
        "telegram_allowed_chat_ids": "-1001",
        "telegram_polling_enabled": True,
    }
    for value in (None, "secret", "short"):
        with pytest.raises(RuntimeError, match="POLL_IDENTITY_SECRET"):
            validate_telegram_settings(
                _settings(**base, telegram_poll_identity_secret=value)
            )

    validate_telegram_settings(
        _settings(
            **base,
            telegram_poll_identity_secret="random-poll-hmac-key-with-at-least-32-chars",
        )
    )
