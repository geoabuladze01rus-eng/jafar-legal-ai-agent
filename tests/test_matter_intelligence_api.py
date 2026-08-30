from datetime import UTC, datetime

from fastapi.testclient import TestClient

from jafar.domains import MatterType
from jafar.legal_models import Matter
from jafar.main import app, matter_store

client = TestClient(app)


def _seed_matter() -> str:
    matter = Matter(
        id="intelligence-test-matter",
        title="Synthetic matter",
        matter_type=MatterType.GENERAL,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    matter_store.create(matter)
    matter_store.add_event(
        matter.id,
        "Synthetic event",
        datetime(2026, 1, 2, tzinfo=UTC),
        source_document="synthetic.txt",
    )
    return matter.id


def test_timeline_is_read_only_and_bounded() -> None:
    matter_id = _seed_matter()
    response = client.get(f"/v1/matters/{matter_id}/intelligence/timeline?limit=1")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_unknown_matter_is_not_disclosed() -> None:
    response = client.get("/v1/matters/unknown/intelligence/evidence")
    assert response.status_code == 404
    assert response.json()["detail"] == "Matter not found"


def test_limit_is_bounded() -> None:
    matter_id = _seed_matter()
    response = client.get(f"/v1/matters/{matter_id}/intelligence/documents?limit=101")
    assert response.status_code == 422
