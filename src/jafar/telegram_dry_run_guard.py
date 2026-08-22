from __future__ import annotations

import os


class ProductionPublicationDisabled(RuntimeError):
    pass


def production_publication_enabled() -> bool:
    return os.getenv("TELEGRAM_PRODUCTION_ENABLED", "false").strip().lower() == "true"


def require_production_publication_enabled() -> None:
    if not production_publication_enabled():
        raise ProductionPublicationDisabled(
            "Production Telegram publication is disabled. Set TELEGRAM_PRODUCTION_ENABLED=true explicitly."
        )
