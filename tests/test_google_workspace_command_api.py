from fastapi.testclient import TestClient

from jafar import main


class FakeWorkspaceService:
    def inbox(self, *, unread_only=False, limit=10):
        return {"message": "Непрочитанных писем: 1.", "count": 1, "messages": [{"id": "m1"}]}

    def calendar_events(self, *, window="week", limit=20):
        return {"message": "В календаре найдено событий: 1.", "count": 1, "window": window, "events": [{"id": "e1"}]}


def test_command_routes_gmail(monkeypatch):
    monkeypatch.setattr(main, "_google_workspace_service", FakeWorkspaceService())
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
    monkeypatch.setattr(main, "_google_workspace_service", FakeWorkspaceService())
    response = TestClient(main.app).post(
        "/v1/command",
        json={"text": "Что у меня завтра в календаре", "user_id": "u1", "source_device": "test"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "calendar_events"
    assert payload["data"]["window"] == "tomorrow"
