from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from jafar import main
from jafar.dashboard import DashboardService
from jafar.domains import MatterType
from jafar.legal_models import Deadline, Matter
from jafar.main import app
from jafar.matters import MatterStore


def _dashboard_store() -> MatterStore:
    store = MatterStore()
    now = datetime(2026, 8, 28, 12, tzinfo=timezone.utc)
    store.create(
        Matter(
            id="case-api",
            title="API дело",
            matter_type=MatterType.CRIMINAL,
            deadlines=[Deadline(title="Срок", due_date=date(2000, 1, 1))],
            created_at=now,
            updated_at=now,
        )
    )
    return store


def test_dashboard_endpoint_exposes_matter_backed_counts(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", None)
    monkeypatch.setattr(main, "dashboard_service", DashboardService(_dashboard_store()))

    response = TestClient(app).get("/v1/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_matters"] == 1
    assert payload["active_matters"] == 1
    assert payload["overdue_deadlines"] == 1
    assert payload["matters"][0]["id"] == "case-api"
    assert payload["signals"][0]["kind"] == "deadline"


def test_v1_dashboard_requires_bearer_key_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", "top-secret")
    monkeypatch.setattr(main, "dashboard_service", DashboardService(_dashboard_store()))
    client = TestClient(app)

    denied = client.get("/v1/dashboard")
    allowed = client.get(
        "/v1/dashboard",
        headers={"Authorization": "Bearer top-secret"},
    )
    health = client.get("/health")

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert health.status_code == 200


def test_production_v1_api_fails_closed_without_authentication(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main.settings, "api_key", None)

    response = TestClient(app).get("/v1/dashboard")

    assert response.status_code == 503
    assert "authentication" in response.json()["detail"].casefold()


def test_production_runtime_rejects_placeholder_or_short_keys(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "environment", "production")

    for value in (None, "replace-me", "short"):
        monkeypatch.setattr(main.settings, "api_key", value)
        with pytest.raises(RuntimeError, match="Production requires"):
            main.validate_runtime_security()

    monkeypatch.setattr(
        main.settings,
        "api_key",
        "this-is-a-long-random-production-key",
    )
    main.validate_runtime_security()
