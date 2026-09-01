from __future__ import annotations

import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse


OAUTH_CALLBACK_PATHS = {"/v1/oauth/google/callback"}
PROTECTED_ENVIRONMENTS = {"staging", "production"}


def configured_api_token() -> str | None:
    token = os.getenv("JAFAR_API_BEARER_TOKEN", "").strip()
    return token or None


def configured_environment() -> str:
    return os.getenv("ENVIRONMENT", "development").strip().lower() or "development"


def api_auth_required() -> bool:
    return configured_api_token() is not None or configured_environment() in PROTECTED_ENVIRONMENTS


def validate_bearer_value(authorization: str | None) -> bool:
    expected = configured_api_token()
    if expected is None:
        return not api_auth_required()
    if not authorization or not authorization.startswith("Bearer "):
        return False
    supplied = authorization.removeprefix("Bearer ").strip()
    return bool(supplied) and hmac.compare_digest(supplied, expected)


async def api_auth_middleware(request: Request, call_next):
    path = request.url.path
    if path in OAUTH_CALLBACK_PATHS:
        return await call_next(request)
    if path.startswith("/v1/") and not validate_bearer_value(request.headers.get("Authorization")):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)
