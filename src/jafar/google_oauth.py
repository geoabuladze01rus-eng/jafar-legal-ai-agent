from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import os
import secrets
from urllib.parse import urlencode

import httpx


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DEFAULT_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
)


@dataclass(frozen=True, slots=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    state_secret: str
    scopes: tuple[str, ...] = DEFAULT_SCOPES

    @classmethod
    def from_env(cls) -> "GoogleOAuthConfig | None":
        client_id = os.getenv("JAFAR_GOOGLE_OAUTH_CLIENT_ID", "").strip()
        client_secret = os.getenv("JAFAR_GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
        redirect_uri = os.getenv("JAFAR_GOOGLE_OAUTH_REDIRECT_URI", "").strip()
        state_secret = os.getenv("JAFAR_GOOGLE_OAUTH_STATE_SECRET", "").strip()
        if not all((client_id, client_secret, redirect_uri, state_secret)):
            return None
        return cls(client_id, client_secret, redirect_uri, state_secret)


@dataclass(frozen=True, slots=True)
class GoogleTokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: datetime
    scope: str | None = None
    token_type: str = "Bearer"

    def is_expiring(self, within_seconds: int = 120) -> bool:
        return self.expires_at <= datetime.now(timezone.utc) + timedelta(seconds=within_seconds)


class GoogleTokenStore:
    """Minimal token-store contract. Production implementations must encrypt refresh tokens."""

    def load(self, subject: str) -> GoogleTokenSet | None:  # pragma: no cover - interface
        raise NotImplementedError

    def save(self, subject: str, token_set: GoogleTokenSet) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class InMemoryGoogleTokenStore(GoogleTokenStore):
    def __init__(self) -> None:
        self._tokens: dict[str, GoogleTokenSet] = {}

    def load(self, subject: str) -> GoogleTokenSet | None:
        return self._tokens.get(subject)

    def save(self, subject: str, token_set: GoogleTokenSet) -> None:
        self._tokens[subject] = token_set


class GoogleOAuthBroker:
    def __init__(self, config: GoogleOAuthConfig, token_store: GoogleTokenStore, client: httpx.Client | None = None) -> None:
        self.config = config
        self.token_store = token_store
        self.client = client or httpx.Client(timeout=20.0)

    def authorization_url(self, subject: str) -> str:
        state = self._sign_state(subject)
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.scopes),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, *, code: str, state: str) -> str:
        subject = self._verify_state(state)
        response = self.client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "redirect_uri": self.config.redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        payload = response.json()
        token_set = self._token_set_from_payload(payload)
        self.token_store.save(subject, token_set)
        return subject

    def access_token(self, subject: str) -> str | None:
        token_set = self.token_store.load(subject)
        if token_set is None:
            return None
        if not token_set.is_expiring():
            return token_set.access_token
        if not token_set.refresh_token:
            return None
        refreshed = self._refresh(token_set.refresh_token)
        self.token_store.save(subject, refreshed)
        return refreshed.access_token

    def _refresh(self, refresh_token: str) -> GoogleTokenSet:
        response = self.client.post(
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        payload = response.json()
        return self._token_set_from_payload(payload, fallback_refresh_token=refresh_token)

    @staticmethod
    def _token_set_from_payload(payload: dict, *, fallback_refresh_token: str | None = None) -> GoogleTokenSet:
        access_token = str(payload.get("access_token", "")).strip()
        if not access_token:
            raise RuntimeError("Google token response did not include access_token")
        expires_in = int(payload.get("expires_in", 3600))
        return GoogleTokenSet(
            access_token=access_token,
            refresh_token=(str(payload.get("refresh_token", "")).strip() or fallback_refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in)),
            scope=(str(payload.get("scope", "")).strip() or None),
            token_type=str(payload.get("token_type", "Bearer")),
        )

    def _sign_state(self, subject: str) -> str:
        payload = {
            "sub": subject,
            "nonce": secrets.token_urlsafe(18),
            "iat": int(datetime.now(timezone.utc).timestamp()),
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
        signature = hmac.new(self.config.state_secret.encode(), encoded, hashlib.sha256).digest()
        return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"

    def _verify_state(self, state: str) -> str:
        try:
            encoded_text, signature_text = state.split(".", 1)
            encoded = encoded_text.encode()
            supplied_signature = base64.urlsafe_b64decode(signature_text + "=" * (-len(signature_text) % 4))
            expected_signature = hmac.new(self.config.state_secret.encode(), encoded, hashlib.sha256).digest()
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ValueError("invalid state signature")
            payload = json.loads(base64.urlsafe_b64decode(encoded_text + "=" * (-len(encoded_text) % 4)))
            issued_at = datetime.fromtimestamp(int(payload["iat"]), tz=timezone.utc)
            if issued_at < datetime.now(timezone.utc) - timedelta(minutes=10):
                raise ValueError("expired state")
            subject = str(payload["sub"]).strip()
            if not subject:
                raise ValueError("empty subject")
            return subject
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid or expired Google OAuth state") from exc
