from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from .google_oauth import GoogleOAuthBroker, GoogleOAuthConfig
from .supabase_google_token_store import build_google_token_store_from_env

router = APIRouter(prefix="/v1/oauth/google", tags=["google-oauth"])

_config = GoogleOAuthConfig.from_env()
_token_store = build_google_token_store_from_env()
_broker = GoogleOAuthBroker(_config, _token_store) if _config is not None else None


def google_oauth_broker() -> GoogleOAuthBroker | None:
    return _broker


@router.get("/start")
def start_google_oauth(subject: str = Query(min_length=1, max_length=200)):
    if _broker is None:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    return RedirectResponse(_broker.authorization_url(subject), status_code=307)


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
