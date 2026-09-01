from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from .api_auth import PROTECTED_ENVIRONMENTS, configured_environment
from .google_oauth import GoogleOAuthBroker, GoogleOAuthConfig
from .supabase_google_token_store import build_google_token_store_from_env

router = APIRouter(prefix="/v1/oauth/google", tags=["google-oauth"])

_config = GoogleOAuthConfig.from_env()
if _config is not None:
    _token_store = build_google_token_store_from_env(
        require_persistent=configured_environment() in PROTECTED_ENVIRONMENTS,
    )
    _broker = GoogleOAuthBroker(_config, _token_store)
else:
    _broker = None


def google_oauth_broker() -> GoogleOAuthBroker | None:
    return _broker


def resolve_google_oauth_subject(requested_subject: str) -> str:
    """Bind OAuth token access to deployment identity in protected environments."""

    configured = (
        os.getenv("JAFAR_GOOGLE_OAUTH_SUBJECT", "").strip()
        or os.getenv("JAFAR_LEGAL_RESEARCH_OWNER_USER_ID", "").strip()
    )
    if configured:
        return configured
    if configured_environment() in PROTECTED_ENVIRONMENTS:
        raise RuntimeError("A fixed Google OAuth subject is required in staging and production")
    return requested_subject


@router.get("/start")
def start_google_oauth(subject: str = Query(min_length=1, max_length=200)):
    if _broker is None:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    try:
        resolved_subject = resolve_google_oauth_subject(subject)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Google OAuth subject is not configured") from exc
    return RedirectResponse(_broker.authorization_url(resolved_subject), status_code=307)


@router.get("/callback")
def google_oauth_callback(code: str, state: str):
    if _broker is None:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    try:
        subject = _broker.exchange_code(code=code, state=state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Google OAuth token exchange failed") from exc
    return {
        "status": "connected",
        "subject": subject,
        "message": "Google Workspace подключён к Джафару. Можно закрыть эту страницу.",
    }
