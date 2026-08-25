from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from .config import settings


API_KEY_HEADER = "X-Jafar-API-Key"


def require_api_key(api_key: str | None = Header(default=None, alias=API_KEY_HEADER)) -> None:
    """Protect private application endpoints while keeping local development usable."""
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
