from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from jafar import main
from jafar.action_approval import ActionApprovalStore, LegalActionApprovalEngine
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


def _patch_approval_services(monkeypatch) -> LegalActionApprovalEngine:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    monkeypatch.setattr(main, "action_approval_store", store)
    monkeypatch.setattr(main, "action_approval_engine", engine)
    return engine


def _development_without_api_key(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", None)


def test_dashboard_endpoint_exposes_matter_backed_counts(monkeypatch) -> None:
    _development_without_api_key(monkeypatch)
    _patch_approval_services(monkeypatch)
    monkeypatch.setattr(main, "dashboard_service", DashboardService(_dashboard_store()))

    response = TestClient(app).get("/v1/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_matters"] == 1
    assert payload["active_matters"] == 1
    assert payload["overdue_deadlines"] == 1
    assert payload["pending_approvals"] == 0
    assert payload["matters"][0]["id"] == "case-api"
    assert payload["signals"][0]["kind"] == "deadline"


def test_pending_approval_is_visible_in_dashboard_and_queue(monkeypatch) -> None:
    _development_without_api_key(monkeypatch)
    engine = _patch_approval_services(monkeypatch)
    monkeypatch.setattr(main, "dashboard_service", DashboardService(MatterStore()))
    engine.propose(
        action_id="mail-1",
        action_type="send_email",
        description="Отправить процессуально значимое письмо",
        evidence_ids=["evidence-1"],
    )
    client = TestClient(app)

    dashboard = client.get("/v1/dashboard")
    approvals = client.get("/v1/approvals?state=proposed")

    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["pending_approvals"] == 1
    assert payload["signals"][0]["kind"] == "approval"
    assert payload["signals"][0]["requires_approval"] is True
    assert approvals.status_code == 200
    assert approvals.json()[0]["action_id"] == "mail-1"
    assert approvals.json()[0]["evidence_ids"] == ["evidence-1"]


def test_approval_decision_removes_pending_signal_but_retains_audit_state(
    monkeypatch,
) -> None:
    _development_without_api_key(monkeypatch)
    engine = _patch_approval_services(monkeypatch)
    monkeypatch.setattr(main, "dashboard_service", DashboardService(MatterStore()))
    engine.propose(
        action_id="mail-approve",
        action_type="send_email",
        description="Отправить ответ доверителю",
    )
    client = TestClient(app)

    decision = client.post(
        "/v1/approvals/mail-approve/approve",
        json={"approver": "lawyer:chernov"},
    )
    dashboard = client.get("/v1/dashboard")
    approved = client.get("/v1/approvals?state=approved")

    assert decision.status_code == 200
    assert decision.json()["state"] == "approved"
    assert decision.json()["decided_by"] == "lawyer:chernov"
    assert dashboard.json()["pending_approvals"] == 0
    assert dashboard.json()["signals"] == []
    assert approved.json()[0]["action_id"] == "mail-approve"
    assert approved.json()[0]["decided_at"]


def test_rejection_requires_reason_and_is_auditable(monkeypatch) -> None:
    _development_without_api_key(monkeypatch)
    engine = _patch_approval_services(monkeypatch)
    engine.propose(
        action_id="motion-reject",
        action_type="file_motion",
        description="Подать ходатайство",
    )
    client = TestClient(app)

    missing_reason = client.post(
        "/v1/approvals/motion-reject/reject",
        json={"approver": "lawyer"},
    )
    rejected = client.post(
        "/v1/approvals/motion-reject/reject",
        json={"approver": "lawyer", "reason": "Требует доработки"},
    )
    history = client.get("/v1/approvals?state=rejected")

    assert missing_reason.status_code == 422
    assert rejected.status_code == 200
    assert rejected.json()["reason"] == "Требует доработки"
    assert history.json()[0]["decision_reason"] == "Требует доработки"


def test_v1_dashboard_requires_bearer_key_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", "top-secret")
    _patch_approval_services(monkeypatch)
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
    monkeypatch.setattr(main.settings, "storage_backend", "supabase")
    main.validate_runtime_security()
