from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient

import jafar.google_oauth_api as google_api


def make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(google_api.router)
    return app


def configure(monkeypatch) -> None:
    monkeypatch.setattr(google_api.settings, "google_oauth_enabled", True)
    monkeypatch.setattr(
        google_api.settings,
        "google_oauth_client_id",
        "client-id.apps.googleusercontent.com",
    )
    monkeypatch.setattr(google_api.settings, "google_oauth_client_secret", "super-secret")
    monkeypatch.setattr(
        google_api.settings,
        "google_oauth_redirect_uri",
        "http://127.0.0.1:8000/v1/integrations/google/callback",
    )
    monkeypatch.setattr(google_api.settings, "google_oauth_scopes", "openid email")


def test_status_never_exposes_client_secret(monkeypatch) -> None:
    configure(monkeypatch)
    client = TestClient(make_app())

    response = client.get("/v1/integrations/google/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["configured"] is True
    assert payload["scopes"] == ["openid", "email"]
    assert "secret" not in response.text.lower()


def test_authorize_returns_google_url_with_one_time_state(monkeypatch) -> None:
    configure(monkeypatch)
    client = TestClient(make_app())

    response = client.get("/v1/integrations/google/authorize")

    assert response.status_code == 200
    url = response.json()["authorization_url"]
    query = parse_qs(urlparse(url).query)
    assert query["client_id"] == ["client-id.apps.googleusercontent.com"]
    assert query["state"][0]
    assert "super-secret" not in url


def test_authorize_fails_closed_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(google_api.settings, "google_oauth_enabled", False)
    client = TestClient(make_app())

    response = client.get("/v1/integrations/google/authorize")

    assert response.status_code == 503


def test_callback_error_does_not_require_authorization_code(monkeypatch) -> None:
    configure(monkeypatch)
    client = TestClient(make_app())

    response = client.get(
        "/v1/integrations/google/callback",
        params={"error": "access_denied", "state": "returned-state"},
    )

    assert response.status_code == 400
    assert "access_denied" in response.json()["detail"]
