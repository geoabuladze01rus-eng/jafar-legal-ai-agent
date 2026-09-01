from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


class GoogleOAuthError(RuntimeError):
    """Raised when the Google OAuth flow cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class GoogleOAuthTokens:
    access_token: str
    refresh_token: str | None
    token_type: str
    expires_at: datetime | None
    scope: str | None = None
    id_token: str | None = None


class OneTimeStateStore:
    """Small in-memory CSRF state store for the single-user local runtime.

    Production deployments should replace this with a shared durable store so
    multiple app instances can consume the same one-time state safely.
    """

    def __init__(self, *, ttl_seconds: int = 600) -> None:
        self.ttl_seconds = ttl_seconds
        self._states: dict[str, float] = {}
        self._lock = threading.Lock()

    def issue(self) -> str:
        now = time.monotonic()
        state = secrets.token_urlsafe(32)
        with self._lock:
            self._purge_expired(now)
            self._states[state] = now + self.ttl_seconds
        return state

    def consume(self, state: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            expires_at = self._states.pop(state, None)
        if expires_at is None or expires_at < now:
            raise GoogleOAuthError("Invalid or expired OAuth state")

    def _purge_expired(self, now: float) -> None:
        expired = [state for state, expires_at in self._states.items() if expires_at < now]
        for state in expired:
            self._states.pop(state, None)


class GoogleOAuthClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: tuple[str, ...],
        prompt: str = "consent",
        state_store: OneTimeStateStore | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not client_id.strip():
            raise ValueError("Google OAuth client_id must not be empty")
        if not client_secret.strip():
            raise ValueError("Google OAuth client_secret must not be empty")
        if not redirect_uri.strip():
            raise ValueError("Google OAuth redirect_uri must not be empty")
        if not scopes:
            raise ValueError("At least one Google OAuth scope is required")

        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self.prompt = prompt
        self.state_store = state_store or OneTimeStateStore()
        self.http_client = http_client or httpx.Client(timeout=30.0)

    def authorization_url(self) -> str:
        state = self.state_store.issue()
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "state": state,
        }
        if self.prompt:
            params["prompt"] = self.prompt
        return f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    def exchange_code(self, *, code: str, state: str) -> GoogleOAuthTokens:
        if not code.strip():
            raise GoogleOAuthError("Google OAuth callback did not include an authorization code")
        self.state_store.consume(state)

        try:
            response = self.http_client.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise GoogleOAuthError("Google OAuth token exchange failed") from exc

        return self._parse_token_payload(payload)

    def refresh(self, refresh_token: str) -> GoogleOAuthTokens:
        if not refresh_token.strip():
            raise GoogleOAuthError("Refresh token must not be empty")
        try:
            response = self.http_client.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise GoogleOAuthError("Google OAuth token refresh failed") from exc

        tokens = self._parse_token_payload(payload)
        if tokens.refresh_token is None:
            return GoogleOAuthTokens(
                access_token=tokens.access_token,
                refresh_token=refresh_token,
                token_type=tokens.token_type,
                expires_at=tokens.expires_at,
                scope=tokens.scope,
                id_token=tokens.id_token,
            )
        return tokens

    @staticmethod
    def _parse_token_payload(payload: object) -> GoogleOAuthTokens:
        if not isinstance(payload, dict):
            raise GoogleOAuthError("Google OAuth returned an unexpected token response")

        access_token = payload.get("access_token")
        token_type = payload.get("token_type", "Bearer")
        refresh_token = payload.get("refresh_token")
        expires_in = payload.get("expires_in")

        if not isinstance(access_token, str) or not access_token:
            raise GoogleOAuthError("Google OAuth token response has no access token")
        if not isinstance(token_type, str) or not token_type:
            raise GoogleOAuthError("Google OAuth token response has an invalid token type")
        if refresh_token is not None and not isinstance(refresh_token, str):
            raise GoogleOAuthError("Google OAuth token response has an invalid refresh token")

        expires_at = None
        if isinstance(expires_in, int) and expires_in > 0:
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        scope = payload.get("scope")
        id_token = payload.get("id_token")
        return GoogleOAuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=token_type,
            expires_at=expires_at,
            scope=scope if isinstance(scope, str) else None,
            id_token=id_token if isinstance(id_token, str) else None,
        )
