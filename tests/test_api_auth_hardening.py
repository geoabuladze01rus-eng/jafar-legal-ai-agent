from fastapi.testclient import TestClient

from jafar import main
from jafar.action_approval import ActionRequest, ActionState


def test_production_middleware_rejects_weak_nonempty_api_key(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main.settings, "api_key", "short-but-nonempty")

    response = TestClient(main.app).get(
        "/v1/dashboard",
        headers={"Authorization": "Bearer short-but-nonempty"},
    )

    assert response.status_code == 503
    assert "securely configured" in response.json()["detail"]


def test_execution_claim_metadata_is_visible_in_server_approval_view() -> None:
    request = ActionRequest(
        action_id="a1",
        action_type="send_email",
        description="Отправить письмо",
        state=ActionState.EXECUTING,
        payload_hash="abc",
        created_at="2026-08-28T12:00:00+00:00",
        decided_at="2026-08-28T12:01:00+00:00",
        decided_by="lawyer",
        execution_claimed_at="2026-08-28T12:02:00+00:00",
        execution_claimed_by="worker-1",
        execution_error=None,
    )

    item = main._approval_item(request)

    assert item.state is ActionState.EXECUTING
    assert item.execution_claimed_by == "worker-1"
    assert item.execution_claimed_at == "2026-08-28T12:02:00+00:00"
