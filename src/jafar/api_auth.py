from __future__ import annotations

import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse


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


async def api_auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/v1/") and not validate_bearer_value(request.headers.get("Authorization")):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)
