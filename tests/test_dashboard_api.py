from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from jafar.dashboard import DashboardService
from jafar.domains import MatterType
from jafar.legal_models import Deadline, Matter
from jafar.main import app
from jafar import main
from jafar.matters import MatterStore


def test_dashboard_endpoint_exposes_matter_backed_counts(monkeypatch) -> None:
    store = MatterStore()
    now = datetime(2026, 8, 28, 12, tzinfo=timezone.utc)
    store.create(
        Matter(
            id="case-api",
            title="API дело",
            matter_type=MatterType.CRIMINAL,
            deadlines=[Deadline(title="Срок", due_date=date(2026, 8, 27))],
            created_at=now,
            updated_at=now,
        )
    )
    monkeypatch.setattr(main, "dashboard_service", DashboardService(store))

    response = TestClient(app).get("/v1/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_matters"] == 1
    assert payload["active_matters"] == 1
    assert payload["overdue_deadlines"] >= 1
    assert payload["matters"][0]["id"] == "case-api"
    assert payload["signals"][0]["kind"] == "deadline"
