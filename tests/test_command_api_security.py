from fastapi.testclient import TestClient

from jafar import main
from jafar.main import app


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", None)
    return TestClient(app)


def test_command_api_rejects_client_controlled_approved_flag(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/v1/command",
        json={
            "text": "покажи мои дела",
            "user_id": "lawyer",
            "source_device": "iphone",
            "approved": True,
        },
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(item["loc"][-1] == "approved" for item in errors)


def test_command_api_accepts_read_only_command_without_approval_field(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/v1/command",
        json={
            "text": "проверка связи",
            "user_id": "lawyer",
            "source_device": "iphone",
        },
    )

    assert response.status_code == 200
    assert response.json()["intent"] == "health"
    assert response.json()["approval_required"] is False


def test_command_api_forbids_unknown_envelope_fields(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/v1/command",
        json={
            "text": "проверка связи",
            "user_id": "lawyer",
            "source_device": "iphone",
            "role": "admin",
        },
    )

    assert response.status_code == 422
