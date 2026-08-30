from fastapi.testclient import TestClient

from jafar import main
from jafar.main import app


def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", None)
    return TestClient(app)


def test_auto_query_rejects_bad_inn_checksum(monkeypatch) -> None:
    response = client(monkeypatch).post(
        "/v1/legal-entities/research-plan",
        json={"query": "7701234567", "query_type": "auto"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid_inn"


def test_auto_query_rejects_bad_ogrn_checksum(monkeypatch) -> None:
    response = client(monkeypatch).post(
        "/v1/legal-entities/research-plan",
        json={"query": "1027700132194", "query_type": "auto"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid_ogrn"


def test_explicit_alphanumeric_kpp_is_normalized(monkeypatch) -> None:
    response = client(monkeypatch).post(
        "/v1/legal-entities/research-plan",
        json={"query": "7707aa001", "query_type": "kpp"},
    )

    assert response.status_code == 200
    assert response.json()["query"] == "7707AA001"
    assert response.json()["query_type"] == "kpp"
