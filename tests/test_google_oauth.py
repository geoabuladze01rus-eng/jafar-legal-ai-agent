from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from jafar.google_oauth import (
    GOOGLE_TOKEN_ENDPOINT,
    GoogleOAuthClient,
    GoogleOAuthError,
    OneTimeStateStore,
)


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_authorization_url_uses_offline_read_only_flow_without_secret() -> None:
    oauth = GoogleOAuthClient(
        client_id="client-id.apps.googleusercontent.com",
        client_secret="super-secret",
        redirect_uri="http://127.0.0.1:8000/v1/integrations/google/callback",
        scopes=(
            "openid",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ),
    )

    url = oauth.authorization_url()
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "accounts.google.com"
    assert query["access_type"] == ["offline"]
    assert query["include_granted_scopes"] == ["true"]
    assert query["prompt"] == ["consent"]
    assert "https://www.googleapis.com/auth/gmail.readonly" in query["scope"][0]
    assert "super-secret" not in url
    assert query["state"][0]


def test_state_is_one_time_and_replay_is_rejected() -> None:
    store = OneTimeStateStore(ttl_seconds=600)
    state = store.issue()
    store.consume(state)

    with pytest.raises(GoogleOAuthError, match="Invalid or expired"):
        store.consume(state)


def test_exchange_code_validates_state_and_parses_tokens() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == GOOGLE_TOKEN_ENDPOINT
        body = request.content.decode()
        assert "client_secret=super-secret" in body
        assert "grant_type=authorization_code" in body
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "openid email",
            },
        )

    store = OneTimeStateStore()
    oauth = GoogleOAuthClient(
        client_id="client-id.apps.googleusercontent.com",
        client_secret="super-secret",
        redirect_uri="http://127.0.0.1:8000/v1/integrations/google/callback",
        scopes=("openid", "email"),
        state_store=store,
        http_client=make_client(handler),
    )
    authorization_url = oauth.authorization_url()
    state = parse_qs(urlparse(authorization_url).query)["state"][0]

    tokens = oauth.exchange_code(code="authorization-code", state=state)

    assert tokens.access_token == "access-token"
    assert tokens.refresh_token == "refresh-token"
    assert tokens.token_type == "Bearer"
    assert tokens.expires_at is not None


def test_exchange_rejects_unknown_state_before_calling_google() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    oauth = GoogleOAuthClient(
        client_id="client-id.apps.googleusercontent.com",
        client_secret="super-secret",
        redirect_uri="http://127.0.0.1:8000/v1/integrations/google/callback",
        scopes=("openid",),
        http_client=make_client(handler),
    )

    with pytest.raises(GoogleOAuthError, match="Invalid or expired"):
        oauth.exchange_code(code="authorization-code", state="not-issued")
    assert called is False


def test_refresh_preserves_original_refresh_token_when_google_omits_new_one() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == GOOGLE_TOKEN_ENDPOINT
        return httpx.Response(
            200,
            json={
                "access_token": "new-access-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )

    oauth = GoogleOAuthClient(
        client_id="client-id.apps.googleusercontent.com",
        client_secret="super-secret",
        redirect_uri="http://127.0.0.1:8000/v1/integrations/google/callback",
        scopes=("openid",),
        http_client=make_client(handler),
    )

    tokens = oauth.refresh("existing-refresh-token")

    assert tokens.access_token == "new-access-token"
    assert tokens.refresh_token == "existing-refresh-token"
