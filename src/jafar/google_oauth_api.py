from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .config import settings
from .google_oauth import (
    GoogleOAuthClient,
    GoogleOAuthError,
    GoogleOAuthTokens,
    OneTimeStateStore,
)

router = APIRouter(prefix="/v1/integrations/google", tags=["google"])
state_store = OneTimeStateStore(ttl_seconds=600)


@dataclass(slots=True)
class _CredentialStore:
    tokens: GoogleOAuthTokens | None = None

    def save(self, tokens: GoogleOAuthTokens) -> None:
        self.tokens = tokens

    def clear(self) -> None:
        self.tokens = None

    @property
    def connected(self) -> bool:
        return self.tokens is not None and bool(self.tokens.refresh_token or self.tokens.access_token)


credential_store = _CredentialStore()


def _scopes() -> tuple[str, ...]:
    return tuple(scope for scope in settings.google_oauth_scopes.split() if scope)


def _client() -> GoogleOAuthClient:
    if not settings.google_oauth_enabled:
        raise HTTPException(status_code=503, detail="Google OAuth integration is disabled")
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth credentials are not configured")

    return GoogleOAuthClient(
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        redirect_uri=settings.google_oauth_redirect_uri,
        scopes=_scopes(),
        prompt=settings.google_oauth_prompt,
        state_store=state_store,
    )


class GoogleOAuthStatus(BaseModel):
    enabled: bool
    configured: bool
    connected: bool
    redirect_uri: str
    scopes: list[str]


class GoogleAuthorizationResponse(BaseModel):
    authorization_url: str


class GoogleCallbackResponse(BaseModel):
    connected: bool
    refresh_token_received: bool


@router.get("/status", response_model=GoogleOAuthStatus)
def status() -> GoogleOAuthStatus:
    configured = bool(settings.google_oauth_client_id and settings.google_oauth_client_secret)
    return GoogleOAuthStatus(
        enabled=settings.google_oauth_enabled,
        configured=configured,
        connected=credential_store.connected,
        redirect_uri=settings.google_oauth_redirect_uri,
        scopes=list(_scopes()),
    )


@router.get("/authorize", response_model=GoogleAuthorizationResponse)
def authorize() -> GoogleAuthorizationResponse:
    client = _client()
    return GoogleAuthorizationResponse(authorization_url=client.authorization_url())


@router.get("/callback", response_model=GoogleCallbackResponse)
def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> GoogleCallbackResponse:
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth authorization failed: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Google OAuth callback is missing code or state")

    try:
        tokens = _client().exchange_code(code=code, state=state)
    except GoogleOAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    credential_store.save(tokens)
    return GoogleCallbackResponse(
        connected=True,
        refresh_token_received=bool(tokens.refresh_token),
    )


@router.post("/disconnect", response_model=GoogleCallbackResponse)
def disconnect() -> GoogleCallbackResponse:
    credential_store.clear()
    return GoogleCallbackResponse(connected=False, refresh_token_received=False)
