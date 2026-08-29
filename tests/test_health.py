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
    payload = response.json()
    assert payload["analysis"]["task"] == "legal_analysis"
    assert payload["persisted"] is False
    assert payload["requires_approval_to_persist"] is True
