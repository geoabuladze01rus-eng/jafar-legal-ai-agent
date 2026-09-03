from fastapi.testclient import TestClient

from jafar import main
from jafar.google_workspace_http import GoogleWorkspaceAPIError, GoogleWorkspaceAuthRequiredError


class FakeWorkspaceService:
    def inbox(self, *, unread_only=False, limit=10):
        return {"message": "Непрочитанных писем: 1.", "count": 1, "messages": [{"id": "m1"}]}

    def calendar_events(self, *, window="week", limit=20):
        return {"message": "В календаре найдено событий: 1.", "count": 1, "window": window, "events": [{"id": "e1"}]}


def test_command_routes_gmail(monkeypatch):
    monkeypatch.setattr(main, "build_google_workspace_service_from_env", lambda subject=None: FakeWorkspaceService())
    response = TestClient(main.app).post(
        "/v1/command",
        json={"text": "Проверь непрочитанные письма", "user_id": "u1", "source_device": "test"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "gmail_inbox"
    assert payload["data"]["count"] == 1
    assert payload["approval_required"] is False


def test_command_routes_calendar(monkeypatch):
    monkeypatch.setattr(main, "build_google_workspace_service_from_env", lambda subject=None: FakeWorkspaceService())
    response = TestClient(main.app).post(
        "/v1/command",
        json={"text": "Что у меня завтра в календаре", "user_id": "u1", "source_device": "test"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "calendar_events"
    assert payload["data"]["window"] == "tomorrow"


def test_command_reports_oauth_required(monkeypatch):
    class UnauthenticatedWorkspace:
        def inbox(self, **kwargs):
            raise GoogleWorkspaceAuthRequiredError("not connected")

        def calendar_events(self, **kwargs):
            raise GoogleWorkspaceAuthRequiredError("not connected")

    monkeypatch.setattr(main, "build_google_workspace_service_from_env", lambda subject=None: UnauthenticatedWorkspace())
    response = TestClient(main.app).post(
        "/v1/command",
        json={"text": "Проверь почту", "user_id": "u1", "source_device": "test"},
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "google_workspace_auth_required"


def test_command_reports_google_api_error_without_requesting_oauth_again(monkeypatch):
    class DisabledGoogleAPI:
        def inbox(self, **kwargs):
            raise GoogleWorkspaceAPIError(status_code=403, kind="api_disabled")

    monkeypatch.setattr(main, "build_google_workspace_service_from_env", lambda subject=None: DisabledGoogleAPI())
    response = TestClient(main.app).post(
        "/v1/command",
        json={"text": "Проверь почту", "user_id": "u1", "source_device": "test"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "google_workspace_api_error"
    assert payload["data"]["google_error_kind"] == "api_disabled"


def test_production_command_uses_server_bound_oauth_subject(monkeypatch):
    subjects = []
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JAFAR_API_BEARER_TOKEN", "synthetic-api-token")
    monkeypatch.setenv("JAFAR_GOOGLE_OAUTH_SUBJECT", "deployment-owner")
    monkeypatch.setattr(
        main,
        "build_google_workspace_service_from_env",
        lambda subject=None: subjects.append(subject) or FakeWorkspaceService(),
    )

    response = TestClient(main.app).post(
        "/v1/command",
        json={
            "text": "Проверь непрочитанные письма",
            "user_id": "caller-controlled-subject",
            "source_device": "test",
        },
        headers={"Authorization": "Bearer synthetic-api-token"},
    )

    assert response.status_code == 200
    assert subjects == ["deployment-owner"]
