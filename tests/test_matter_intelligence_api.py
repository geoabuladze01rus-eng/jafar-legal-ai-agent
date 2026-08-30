from datetime import UTC, datetime

from fastapi.testclient import TestClient

from jafar.domains import MatterType
from jafar.legal_models import Matter
from jafar.main import app, intelligence_store, matter_store

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


def test_evidence_reads_persisted_candidate_with_owner_scope() -> None:
    matter_id = _seed_matter()
    intelligence_store.append(
        owner_id="local-development-user",
        matter_id=matter_id,
        kind="evidence",
        analysis_run_id="run-1",
        payload={
            "id": "e-1",
            "summary": "Synthetic candidate",
            "source_document_id": "doc-1",
            "page_or_fragment": "p. 1",
            "confidence": 0.6,
            "verification_state": "candidate",
        },
    )
    response = client.get(f"/v1/matters/{matter_id}/intelligence/evidence")
    assert response.status_code == 200
    assert response.json()["items"][0]["verification_state"] == "candidate"


def test_evidence_does_not_cross_owner_scope() -> None:
    matter_id = _seed_matter()
    intelligence_store.append(
        owner_id="other-owner",
        matter_id=matter_id,
        kind="evidence",
        analysis_run_id="run-other",
        payload={"id": "e-other", "summary": "hidden"},
    )
    response = client.get(f"/v1/matters/{matter_id}/intelligence/evidence")
    assert response.status_code == 200
    assert all(item["id"] != "e-other" for item in response.json()["items"])
