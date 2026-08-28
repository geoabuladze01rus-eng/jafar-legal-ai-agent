from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

from jafar import main
from jafar.config import settings
from jafar.domains import MatterType
from jafar.legal_models import Deadline, Matter


def test_deadlines_contract_and_date_only(monkeypatch):
    now = datetime.now(UTC); matter = Matter(id="m-deadline", title="Synthetic", matter_type=MatterType.GENERAL, created_at=now, updated_at=now, deadlines=[Deadline(title="Срок", due_date=date(2026, 9, 15), source_text=None)])
    monkeypatch.setattr(main.matter_store, "get", lambda value: matter if value == matter.id else None)
    monkeypatch.setattr(settings, "api_key", "deadline-secret")
    with TestClient(main.app) as client:
        response = client.get(f"/v1/matters/{matter.id}/deadlines", headers={"X-Jafar-API-Key":"deadline-secret"})
    assert response.status_code == 200
    assert response.json() == [{"title":"Срок", "due_date":"2026-09-15", "source_text":None}]

def test_deadlines_auth_and_missing_matter(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "deadline-secret")
    with TestClient(main.app) as client:
        assert client.get("/v1/matters/missing/deadlines").status_code == 401
        assert client.get("/v1/matters/missing/deadlines", headers={"X-Jafar-API-Key":"deadline-secret"}).status_code == 404
