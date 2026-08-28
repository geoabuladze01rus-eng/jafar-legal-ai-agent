from datetime import UTC, datetime

from fastapi.testclient import TestClient

from jafar import main
from jafar.config import settings
from jafar.domains import MatterType
from jafar.legal_models import Matter


def test_documents_endpoint_metadata_and_empty(monkeypatch):
    now = datetime.now(UTC)
    matter = Matter(id="m-test", title="Synthetic matter", matter_type=MatterType.GENERAL, created_at=now, updated_at=now)
    class Repo:
        def list_for_matter(self, matter_id):
            return [{"id":"d1","matter_id":matter_id,"filename":"synthetic.pdf","content_type":"application/pdf","source":"test","created_at":now.isoformat(),"processing_status":"stored"}]
    monkeypatch.setattr(main.matter_store, "get", lambda value: matter if value == matter.id else None)
    monkeypatch.setattr(main, "document_repository", Repo())
    monkeypatch.setattr(settings, "api_key", "test-secret")
    with TestClient(main.app) as client:
        response = client.get(f"/v1/matters/{matter.id}/documents", headers={"X-Jafar-API-Key":"test-secret"})
    assert response.status_code == 200
    assert set(response.json()[0]) == {"id","matter_id","filename","content_type","source","created_at","processing_status"}

def test_documents_endpoint_auth_and_missing_matter(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-secret")
    with TestClient(main.app) as client:
        assert client.get("/v1/matters/missing/documents").status_code == 401
        assert client.get("/v1/matters/missing/documents", headers={"X-Jafar-API-Key":"test-secret"}).status_code == 404
