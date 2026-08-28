from datetime import UTC, datetime

from fastapi.testclient import TestClient

from jafar import main
from jafar.config import settings
from jafar.domains import MatterType
from jafar.legal_models import Matter


def test_legal_position_empty_contract_and_isolation(monkeypatch):
    now = datetime.now(UTC); matter = Matter(id="m-pos", title="Synthetic", matter_type=MatterType.GENERAL, created_at=now, updated_at=now)
    monkeypatch.setattr(main.matter_store, "get", lambda value: matter if value == matter.id else None)
    monkeypatch.setattr(settings, "api_key", "position-secret")
    with TestClient(main.app) as client:
        response = client.get(f"/v1/matters/{matter.id}/legal-position", headers={"X-Jafar-API-Key":"position-secret"})
        missing = client.get("/v1/matters/other/legal-position", headers={"X-Jafar-API-Key":"position-secret"})
    assert response.status_code == 200
    assert response.json() == {"matter_id":"m-pos", "summary":None, "items":[]}
    assert missing.status_code == 404

def test_legal_position_requires_auth(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "position-secret")
    with TestClient(main.app) as client:
        assert client.get("/v1/matters/m-pos/legal-position").status_code == 401
