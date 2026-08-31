from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def configured_api_token() -> str | None:
    token = os.getenv("JAFAR_API_BEARER_TOKEN", "").strip()
    return token or None


def require_api_auth(authorization: str | None = Header(default=None)) -> None:
    expected = configured_api_token()
    if expected is None:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    supplied = authorization.removeprefix("Bearer ").strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid bearer token")
