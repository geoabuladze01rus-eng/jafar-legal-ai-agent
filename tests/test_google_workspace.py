from datetime import datetime, timezone

from jafar.google_workspace import (
    GoogleWorkspaceService,
    NaturalLanguageWorkspaceRouter,
    WorkspaceEvent,
    WorkspaceMail,
)


class FakeGmail:
    def list_inbox(self, *, limit=10, unread_only=False):
        return [
            WorkspaceMail(
                message_id="m1",
                sender="court@example.ru",
                subject="Судебное заседание",
                snippet="Назначено заседание",
                received_at="2026-08-31T08:00:00+03:00",
                unread=unread_only,
            )
        ]


class FakeCalendar:
    def list_events(self, *, time_min, time_max, limit=20):
        return [
            WorkspaceEvent(
                event_id="e1",
                title="Заседание по делу",
                starts_at="2026-09-01T12:00:00+03:00",
            )
        ]


def test_router_detects_unread_mail():
    route = NaturalLanguageWorkspaceRouter().route("Джафар, проверь непрочитанные письма")
    assert route.intent == "gmail_inbox"
    assert route.unread_only is True


def test_router_detects_tomorrow_calendar():
    route = NaturalLanguageWorkspaceRouter().route("Что у меня завтра в календаре?")
    assert route.intent == "calendar_events"
    assert route.window == "tomorrow"


def test_workspace_service_returns_mail_summary():
    data = GoogleWorkspaceService(gmail=FakeGmail()).inbox(unread_only=True)
    assert data["count"] == 1
    assert data["messages"][0]["subject"] == "Судебное заседание"


def test_workspace_service_returns_calendar_window():
    service = GoogleWorkspaceService(calendar=FakeCalendar())
    data = service.calendar_events(
        window="tomorrow",
        now=datetime(2026, 8, 31, 10, tzinfo=timezone.utc),
    )
    assert data["count"] == 1
    assert data["window"] == "tomorrow"
