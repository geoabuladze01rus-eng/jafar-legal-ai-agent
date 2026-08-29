from fastapi.testclient import TestClient

from jafar.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_analysis_boundary() -> None:
    response = client.post("/v1/analyze", json={"text": "Тест документа"})
    assert response.status_code == 200
    assert response.json()["task"] == "legal_analysis"
