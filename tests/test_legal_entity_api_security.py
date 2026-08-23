from fastapi.testclient import TestClient

from jafar.config import settings
from jafar.main import app


def test_legal_entity_api_rejects_missing_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "staging")
    monkeypatch.setattr(settings, "api_key", "test-secret")

    with TestClient(app) as client:
        response = client.post(
            "/v1/legal-entities/research-plan",
            json={"query": "ООО Альфа"},
        )

    assert response.status_code == 401
