from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from .config import settings


API_KEY_HEADER = "X-Jafar-API-Key"


def require_api_key(api_key: str | None = Header(default=None, alias=API_KEY_HEADER)) -> None:
    """Protect application endpoints without putting credentials in source control.

    Development remains usable without configuration so the local-first workflow
    keeps working. Every non-development environment must have a configured key.
    """
    configured_key = settings.api_key
    if not configured_key:
        if settings.environment.lower() == "development":
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured",
        )

    if not api_key or not hmac.compare_digest(api_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
