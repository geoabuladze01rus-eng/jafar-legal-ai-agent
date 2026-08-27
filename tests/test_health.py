from fastapi.testclient import TestClient

from jafar import __version__
from jafar.config import settings
from jafar.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_service_and_package_versions_are_aligned() -> None:
    assert app.version == __version__ == "0.7.0"


def test_analysis_boundary(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_key", "test-secret")
    response = client.post(
        "/v1/analyze",
        json={"text": "Тест документа"},
        headers={"X-Jafar-API-Key": "test-secret"},
    )
    assert response.status_code == 200
    assert response.json()["analysis"]["task"] == "legal_analysis"
