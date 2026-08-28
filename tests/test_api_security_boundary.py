from fastapi.testclient import TestClient

from jafar import main
from jafar.main import app


def _development_without_api_key(monkeypatch) -> TestClient:
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", None)
    return TestClient(app)


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
    client = _development_without_api_key(monkeypatch)

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
    client = _development_without_api_key(monkeypatch)
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


def test_client_supplied_entity_findings_cannot_fabricate_scored_risk(monkeypatch) -> None:
    client = _development_without_api_key(monkeypatch)

    response = client.post(
        "/v1/legal-entities/profile",
        json={
            "query": "ООО Ромашка",
            "query_type": "name",
            "findings": [
                {
                    "source_key": "fedresurs",
                    "status": "found",
                    "title": "Поддельное банкротство",
                    "details": {"bankruptcy": True},
                },
                {
                    "source_key": "fssp",
                    "status": "found",
                    "title": "Поддельный долг",
                    "details": {"debt_amount": 999999999},
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_trust"] == "client_supplied_unverified"
    assert payload["risk_assessment_status"] == "not_scored_unverified_input"
    assert payload["risk_score"] is None
    assert payload["risk_level"] == "unverified"
    assert payload["risks"] == []
    assert payload["sources_found"] == 2


def test_legal_entity_profile_bounds_detail_keys(monkeypatch) -> None:
    client = _development_without_api_key(monkeypatch)

    response = client.post(
        "/v1/legal-entities/profile",
        json={
            "query": "ООО Ромашка",
            "query_type": "name",
            "findings": [
                {
                    "source_key": "registry",
                    "status": "found",
                    "title": "Слишком большой набор полей",
                    "details": {f"key-{index}": index for index in range(101)},
                }
            ],
        },
    )

    assert response.status_code == 422


def test_entity_query_auto_detects_inn_ogrn_and_kpp(monkeypatch) -> None:
    client = _development_without_api_key(monkeypatch)

    cases = (
        ("7707083893", "inn"),
        ("500100732259", "inn"),
        ("1027700132195", "ogrn"),
        ("304500116000157", "ogrn"),
        ("770701001", "kpp"),
    )
    for value, expected_type in cases:
        response = client.post(
            "/v1/legal-entities/research-plan",
            json={"query": value, "query_type": "auto"},
        )
        assert response.status_code == 200
        assert response.json()["query"] == value
        assert response.json()["query_type"] == expected_type


def test_explicit_invalid_entity_identifier_returns_422_not_500(monkeypatch) -> None:
    client = _development_without_api_key(monkeypatch)

    response = client.post(
        "/v1/legal-entities/research-plan",
        json={"query": "123", "query_type": "inn"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid_inn"


def test_entity_profile_returns_normalized_auto_query_type(monkeypatch) -> None:
    client = _development_without_api_key(monkeypatch)

    response = client.post(
        "/v1/legal-entities/profile",
        json={"query": "770701001", "query_type": "auto", "findings": []},
    )

    assert response.status_code == 200
    assert response.json()["query"] == "770701001"
    assert response.json()["query_type"] == "kpp"


def test_entity_profile_rejects_unsafe_client_source_url(monkeypatch) -> None:
    client = _development_without_api_key(monkeypatch)

    response = client.post(
        "/v1/legal-entities/profile",
        json={
            "query": "ООО Ромашка",
            "query_type": "name",
            "findings": [
                {
                    "source_key": "open_web",
                    "status": "found",
                    "title": "Unsafe URL",
                    "source_url": "http://127.0.0.1/internal",
                    "details": {},
                }
            ],
        },
    )

    assert response.status_code == 422


def test_entity_profile_normalizes_source_key(monkeypatch) -> None:
    client = _development_without_api_key(monkeypatch)

    response = client.post(
        "/v1/legal-entities/profile",
        json={
            "query": "ООО Ромашка",
            "query_type": "name",
            "findings": [
                {
                    "source_key": "  FSSP  ",
                    "status": "no_data",
                    "title": "ФССП",
                    "details": {},
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["findings"][0]["source_key"] == "fssp"
