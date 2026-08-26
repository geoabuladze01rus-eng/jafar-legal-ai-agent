from fastapi.testclient import TestClient

from jafar.config import settings
from jafar.main import app


def _command_payload() -> dict[str, str]:
    return {"text": "проверка связи", "user_id": "local", "source_device": "mac"}


def test_health_is_public() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_development_allows_local_api_without_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "api_key", None)

    with TestClient(app) as client:
        response = client.post("/v1/command", json=_command_payload())

    assert response.status_code == 200
    assert response.json()["intent"] == "health"


def test_non_development_requires_configured_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "staging")
    monkeypatch.setattr(settings, "api_key", None)

    with TestClient(app) as client:
        response = client.post("/v1/command", json=_command_payload())

    assert response.status_code == 503


def test_configured_key_is_required_and_constant_time_checked(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "staging")
    monkeypatch.setattr(settings, "api_key", "test-secret")

    with TestClient(app) as client:
        missing = client.post("/v1/command", json=_command_payload())
        wrong = client.post(
            "/v1/command",
            json=_command_payload(),
            headers={"X-Jafar-API-Key": "wrong"},
        )
        valid = client.post(
            "/v1/command",
            json=_command_payload(),
            headers={"X-Jafar-API-Key": "test-secret"},
        )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert valid.status_code == 200
    assert valid.json()["intent"] == "health"


def test_legal_entity_routes_share_auth_boundary(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "staging")
    monkeypatch.setattr(settings, "api_key", "test-secret")

    with TestClient(app) as client:
        response = client.post(
            "/v1/legal-entities/research-plan",
            json={"query": "ООО Альфа"},
        )

    assert response.status_code == 401
