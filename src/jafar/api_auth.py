from __future__ import annotations

import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse


OAUTH_CALLBACK_PATHS = {"/v1/oauth/google/callback"}
PROTECTED_ENVIRONMENTS = {"staging", "production"}
DESKTOP_RUNTIME_MODE = "desktop"


def configured_api_token() -> str | None:
    token = os.getenv("JAFAR_API_BEARER_TOKEN", "").strip()
    return token or None


def configured_environment() -> str:
    return os.getenv("ENVIRONMENT", "development").strip().lower() or "development"


def is_desktop_runtime() -> bool:
    return os.getenv("JAFAR_RUNTIME_MODE", "").strip().lower() == DESKTOP_RUNTIME_MODE


def configured_desktop_ipc_token() -> str | None:
    token = os.getenv("JAFAR_DESKTOP_IPC_TOKEN", "").strip()
    return token or None


def api_auth_required() -> bool:
    return (
        is_desktop_runtime()
        or configured_api_token() is not None
        or configured_environment() in PROTECTED_ENVIRONMENTS
    )


def validate_bearer_value(authorization: str | None) -> bool:
    if is_desktop_runtime():
        expected = configured_desktop_ipc_token()
        if expected is None or not authorization or not authorization.startswith("Bearer "):
            return False
        supplied = authorization.removeprefix("Bearer ").strip()
        return bool(supplied) and hmac.compare_digest(supplied, expected)
    expected = configured_api_token()
    if expected is None:
        return not api_auth_required()
    if not authorization or not authorization.startswith("Bearer "):
        return False
    supplied = authorization.removeprefix("Bearer ").strip()
    return bool(supplied) and hmac.compare_digest(supplied, expected)


async def api_auth_middleware(request: Request, call_next):
    path = request.url.path
    # Production OAuth redirects keep their narrow callback exemption.  The desktop
    # sidecar has no OAuth bootstrap surface and authenticates every private route.
    if path in OAUTH_CALLBACK_PATHS and not is_desktop_runtime():
        return await call_next(request)
    if path.startswith("/v1/") and not validate_bearer_value(request.headers.get("Authorization")):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)
