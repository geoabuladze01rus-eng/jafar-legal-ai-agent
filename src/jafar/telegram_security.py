from __future__ import annotations

from .config import Settings


def configured_chat_ids(settings: Settings) -> tuple[str, ...]:
    return tuple(
        sorted({part.strip() for part in settings.telegram_allowed_chat_ids.split(",") if part.strip()})
    )


def live_send_enabled(settings: Settings) -> bool:
    return bool(settings.telegram_production_send and not settings.telegram_dry_run)


def validate_telegram_settings(settings: Settings) -> None:
    """Fail early on contradictory or incomplete Telegram execution configuration."""

    token_present = bool((settings.telegram_bot_token or "").strip())
    allowed = configured_chat_ids(settings)

    if settings.telegram_polling_enabled and not token_present:
        raise RuntimeError("TELEGRAM_POLLING_ENABLED requires TELEGRAM_BOT_TOKEN")
    if settings.telegram_scheduler_enabled and not token_present:
        raise RuntimeError("TELEGRAM_SCHEDULER_ENABLED requires TELEGRAM_BOT_TOKEN")

    if settings.telegram_production_send:
        if settings.telegram_dry_run:
            raise RuntimeError(
                "TELEGRAM_PRODUCTION_SEND=true conflicts with TELEGRAM_DRY_RUN=true; choose live or dry-run explicitly"
            )
        if not token_present:
            raise RuntimeError("Telegram live send requires TELEGRAM_BOT_TOKEN")
        if not allowed:
            raise RuntimeError("Telegram live send requires TELEGRAM_ALLOWED_CHAT_IDS")

    if settings.environment.strip().casefold() == "production":
        if settings.telegram_polling_enabled and not allowed:
            raise RuntimeError("Production Telegram polling requires TELEGRAM_ALLOWED_CHAT_IDS")
        if settings.telegram_scheduler_enabled and not allowed:
            raise RuntimeError("Production Telegram scheduler requires TELEGRAM_ALLOWED_CHAT_IDS")
