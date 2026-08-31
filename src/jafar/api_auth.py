from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request


def configured_api_token() -> str | None:
    token = os.getenv("JAFAR_API_BEARER_TOKEN", "").strip()
    return token or None


def validate_bearer_value(authorization: str | None) -> bool:
    expected = configured_api_token()
    if expected is None:
        return True
    if not authorization or not authorization.startswith("Bearer "):
        return False
    supplied = authorization.removeprefix("Bearer ").strip()
    return bool(supplied) and hmac.compare_digest(supplied, expected)


def require_api_auth(request: Request) -> None:
    if not validate_bearer_value(request.headers.get("Authorization")):
        raise HTTPException(status_code=401, detail="Unauthorized")
