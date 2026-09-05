from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
import re


@dataclass(frozen=True, slots=True)
class WorkspaceMail:
    message_id: str
    sender: str
    subject: str
    snippet: str
    received_at: str | None = None
    unread: bool = False


@dataclass(frozen=True, slots=True)
class WorkspaceEvent:
    event_id: str
    title: str
    starts_at: str
    ends_at: str | None = None
    location: str | None = None


class GmailReadProvider(Protocol):
    def list_inbox(self, *, limit: int = 10, unread_only: bool = False) -> list[WorkspaceMail]: ...


class CalendarReadProvider(Protocol):
    def list_events(self, *, time_min: datetime, time_max: datetime, limit: int = 20) -> list[WorkspaceEvent]: ...


@dataclass(frozen=True, slots=True)
class WorkspaceRoute:
    intent: str | None
    unread_only: bool = False
    window: str | None = None


class NaturalLanguageWorkspaceRouter:
    """Conservative read-only routing for Gmail and Google Calendar."""

    MAIL_MARKERS = ("проверь почт", "входящ", "письм", "почта", "email", "gmail")
    CALENDAR_MARKERS = ("календар", "расписан", "встреч", "событ", "заседан", "что у меня сегодня", "что у меня завтра")

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.casefold().replace("ё", "е").split())

    def route(self, text: str) -> WorkspaceRoute:
        normalized = self._normalize(text)
        if any(marker in normalized for marker in self.MAIL_MARKERS):
            unread_only = any(marker in normalized for marker in ("непрочитан", "новые письма", "новую почту"))
            return WorkspaceRoute(intent="gmail_inbox", unread_only=unread_only)
        if any(marker in normalized for marker in self.CALENDAR_MARKERS):
            window = "week"
            if "сегодня" in normalized:
                window = "today"
            elif "завтра" in normalized:
                window = "tomorrow"
            elif re.search(r"\bнедел", normalized):
                window = "week"
            return WorkspaceRoute(intent="calendar_events", window=window)
        return WorkspaceRoute(intent=None)


@dataclass(slots=True)
class GoogleWorkspaceService:
    gmail: GmailReadProvider | None = None
    calendar: CalendarReadProvider | None = None

    def inbox(self, *, unread_only: bool = False, limit: int = 10) -> dict:
        if self.gmail is None:
            raise RuntimeError("Gmail is not configured")
        messages = self.gmail.list_inbox(limit=limit, unread_only=unread_only)
        return {
            "message": self._mail_message(messages, unread_only),
            "count": len(messages),
            "messages": [
                {
                    "id": item.message_id,
                    "sender": item.sender,
                    "subject": item.subject,
                    "snippet": item.snippet,
                    "received_at": item.received_at,
                    "unread": item.unread,
                }
                for item in messages
            ],
        }

    def calendar_events(self, *, window: str = "week", now: datetime | None = None, limit: int = 20) -> dict:
        if self.calendar is None:
            raise RuntimeError("Google Calendar is not configured")
        current = now or datetime.now(timezone.utc)
        start, end = self._window(current, window)
        events = self.calendar.list_events(time_min=start, time_max=end, limit=limit)
        return {
            "message": f"В календаре найдено событий: {len(events)}.",
            "count": len(events),
            "window": window,
            "events": [
                {
                    "id": item.event_id,
                    "title": item.title,
                    "starts_at": item.starts_at,
                    "ends_at": item.ends_at,
                    "location": item.location,
                }
                for item in events
            ],
        }

    @staticmethod
    def _mail_message(messages: list[WorkspaceMail], unread_only: bool) -> str:
        if not messages:
            return "Непрочитанных писем нет." if unread_only else "Во входящих писем не найдено."
        prefix = "Непрочитанных" if unread_only else "Во входящих"
        return f"{prefix} писем: {len(messages)}."

    @staticmethod
    def _window(now: datetime, window: str) -> tuple[datetime, datetime]:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        if window == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return start, start + timedelta(days=1)
        if window == "tomorrow":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return start, start + timedelta(days=1)
        return now, now + timedelta(days=7)
