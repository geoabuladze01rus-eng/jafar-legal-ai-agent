from fastapi.testclient import TestClient

from jafar import main
from jafar.main import app


def test_legal_entity_routes_share_v1_bearer_boundary(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", "test-api-key")
    client = TestClient(app)

    denied = client.post(
        "/v1/legal-entities/research-plan",
        json={"query": "7707083893", "query_type": "inn"},
    )
    allowed = client.post(
        "/v1/legal-entities/research-plan",
        json={"query": "7707083893", "query_type": "inn"},
        headers={"Authorization": "Bearer test-api-key"},
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_production_middleware_rejects_weak_key_even_if_lifespan_is_bypassed(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main.settings, "api_key", "short")
    client = TestClient(app)

    response = client.get(
        "/v1/dashboard",
        headers={"Authorization": "Bearer short"},
    )

    assert response.status_code == 503
    assert "securely configured" in response.json()["detail"]


def test_legal_entity_requests_fail_closed_on_unknown_fields(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", None)
    client = TestClient(app)

    response = client.post(
        "/v1/legal-entities/research-plan",
        json={
            "query": "ООО Ромашка",
            "query_type": "name",
            "client_can_override_server_policy": True,
        },
    )

    assert response.status_code == 422


def test_legal_entity_profile_bounds_findings(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", None)
    client = TestClient(app)
    finding = {
        "source_key": "registry",
        "status": "found",
        "title": "Запись",
        "details": {},
    }

    response = client.post(
        "/v1/legal-entities/profile",
        json={
            "query": "ООО Ромашка",
            "query_type": "name",
            "findings": [finding for _ in range(101)],
        },
    )

    assert response.status_code == 422
