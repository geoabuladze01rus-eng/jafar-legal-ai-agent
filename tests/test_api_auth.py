from fastapi import FastAPI
from fastapi.testclient import TestClient

from jafar.api_auth import api_auth_middleware, configured_api_token, validate_bearer_value


def test_auth_disabled_when_token_is_not_configured(monkeypatch):
    monkeypatch.delenv("JAFAR_API_BEARER_TOKEN", raising=False)
    assert configured_api_token() is None
    assert validate_bearer_value(None) is True


def test_auth_accepts_matching_bearer_token(monkeypatch):
    monkeypatch.setenv("JAFAR_API_BEARER_TOKEN", "secret-token")
    assert validate_bearer_value("Bearer secret-token") is True


def test_auth_rejects_missing_or_wrong_token(monkeypatch):
    monkeypatch.setenv("JAFAR_API_BEARER_TOKEN", "secret-token")
    assert validate_bearer_value(None) is False
    assert validate_bearer_value("Basic secret-token") is False
    assert validate_bearer_value("Bearer wrong-token") is False


def test_google_oauth_callback_is_exempt_but_other_v1_routes_are_protected(monkeypatch):
    monkeypatch.setenv("JAFAR_API_BEARER_TOKEN", "secret-token")
    app = FastAPI()
    app.middleware("http")(api_auth_middleware)

    @app.get("/v1/oauth/google/callback")
    def google_callback():
        return {"status": "connected"}

    @app.get("/v1/protected")
    def protected():
        return {"status": "ok"}

    client = TestClient(app)
    assert client.get("/v1/oauth/google/callback").status_code == 200
    assert client.get("/v1/protected").status_code == 401
    assert client.get("/v1/protected", headers={"Authorization": "Bearer secret-token"}).status_code == 200
