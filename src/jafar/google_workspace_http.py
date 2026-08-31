from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
import os
from typing import Callable

import httpx

from .google_oauth import GoogleOAuthAuthorizationError, GoogleOAuthError
from .google_workspace import WorkspaceEvent, WorkspaceMail


class GoogleWorkspaceError(RuntimeError):
    """Base error for a Google Workspace read operation."""


class GoogleWorkspaceAuthRequiredError(GoogleWorkspaceError):
    """No usable authorization remains for the requested Workspace subject."""


class GoogleWorkspaceNetworkError(GoogleWorkspaceError):
    """The Google API could not be reached."""


class GoogleWorkspaceAPIError(GoogleWorkspaceError):
    """A Google API response failed without carrying sensitive response content."""

    def __init__(self, *, status_code: int, kind: str = "api_error") -> None:
        self.status_code = status_code
        self.kind = kind
        super().__init__("Google API request failed")


class GoogleWorkspacePayloadError(GoogleWorkspaceError):
    """Google returned a response that cannot be used safely."""


@dataclass(slots=True)
class GoogleHTTPClient:
    access_token: str | None = None
    access_token_provider: Callable[[], str | None] | None = None
    client: httpx.Client | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = httpx.Client(timeout=20.0)

    def _current_access_token(self) -> str:
        try:
            token = self.access_token_provider() if self.access_token_provider is not None else self.access_token
        except GoogleOAuthAuthorizationError as exc:
            raise GoogleWorkspaceAuthRequiredError("Google authorization is no longer valid") from exc
        except GoogleOAuthError as exc:
            raise GoogleWorkspaceNetworkError("Google OAuth refresh failed") from exc
        token = (token or "").strip()
        if not token:
            raise GoogleWorkspaceAuthRequiredError("Google Workspace is not connected")
        return token

    def get(self, url: str, *, params: dict | None = None) -> dict:
        try:
            response = self.client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self._current_access_token()}", "Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except GoogleWorkspaceError:
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise GoogleWorkspaceAuthRequiredError("Google authorization is no longer valid") from exc
            raise GoogleWorkspaceAPIError(
                status_code=exc.response.status_code,
                kind=self._error_kind(exc.response),
            ) from exc
        except httpx.RequestError as exc:
            raise GoogleWorkspaceNetworkError("Google API network request failed") from exc
        except ValueError as exc:
            raise GoogleWorkspacePayloadError("Google API returned an invalid payload") from exc
        if not isinstance(payload, dict):
            raise GoogleWorkspacePayloadError("Google API returned an invalid payload")
        return payload

    @staticmethod
    def _error_kind(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return "api_error"
        error = payload.get("error") if isinstance(payload, dict) else None
        reasons = error.get("errors", []) if isinstance(error, dict) else []
        reason = str(reasons[0].get("reason", "")).casefold() if reasons else ""
        if reason in {"accessnotconfigured", "service_disabled", "servicedisabled"}:
            return "api_disabled"
        if reason in {
            "access_token_scope_insufficient",
            "insufficientpermissions",
            "insufficient_scope",
        }:
            return "insufficient_scope"
        return "api_error"


@dataclass(slots=True)
class GmailHTTPProvider:
    transport: GoogleHTTPClient

    def list_inbox(self, *, limit: int = 10, unread_only: bool = False) -> list[WorkspaceMail]:
        query = "in:inbox"
        if unread_only:
            query += " is:unread"
        payload = self.transport.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            params={"q": query, "maxResults": max(1, min(limit, 50))},
        )
        result: list[WorkspaceMail] = []
        for row in payload.get("messages", [])[:limit]:
            message_id = str(row.get("id", ""))
            if not message_id:
                continue
            result.append(self._fetch_metadata(message_id))
        return result

    def _fetch_metadata(self, message_id: str) -> WorkspaceMail:
        payload = self.transport.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
            params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
        )
        headers = {
            str(item.get("name", "")).casefold(): str(item.get("value", ""))
            for item in payload.get("payload", {}).get("headers", [])
        }
        received_at = None
        if headers.get("date"):
            try:
                received_at = parsedate_to_datetime(headers["date"]).isoformat()
            except (TypeError, ValueError, OverflowError):
                received_at = headers["date"]
        labels = {str(label) for label in payload.get("labelIds", [])}
        return WorkspaceMail(
            message_id=message_id,
            sender=headers.get("from", ""),
            subject=headers.get("subject", "(без темы)"),
            snippet=str(payload.get("snippet", "")),
            received_at=received_at,
            unread="UNREAD" in labels,
        )


@dataclass(slots=True)
class GoogleCalendarHTTPProvider:
    transport: GoogleHTTPClient
    calendar_id: str = "primary"

    def list_events(self, *, time_min: datetime, time_max: datetime, limit: int = 20) -> list[WorkspaceEvent]:
        payload = self.transport.get(
            f"https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}/events",
            params={
                "timeMin": time_min.isoformat(),
                "timeMax": time_max.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": max(1, min(limit, 50)),
            },
        )
        result: list[WorkspaceEvent] = []
        for item in payload.get("items", []):
            start = item.get("start", {})
            end = item.get("end", {})
            result.append(
                WorkspaceEvent(
                    event_id=str(item.get("id", "")),
                    title=str(item.get("summary") or "(без названия)"),
                    starts_at=str(start.get("dateTime") or start.get("date") or ""),
                    ends_at=str(end.get("dateTime") or end.get("date") or "") or None,
                    location=str(item.get("location") or "") or None,
                )
            )
        return result


def build_google_workspace_service_from_env(subject: str | None = None):
    from .google_workspace import GoogleWorkspaceService

    if subject:
        from .google_oauth_api import google_oauth_broker

        broker = google_oauth_broker()
        if broker is not None:
            transport = GoogleHTTPClient(access_token_provider=lambda: broker.access_token(subject))
            return GoogleWorkspaceService(
                gmail=GmailHTTPProvider(transport),
                calendar=GoogleCalendarHTTPProvider(transport),
            )

    gmail_token = os.getenv("JAFAR_GMAIL_ACCESS_TOKEN", "").strip()
    calendar_token = os.getenv("JAFAR_GOOGLE_CALENDAR_ACCESS_TOKEN", "").strip()
    shared_token = os.getenv("JAFAR_GOOGLE_ACCESS_TOKEN", "").strip()

    gmail = None
    calendar = None
    if gmail_token or shared_token:
        gmail = GmailHTTPProvider(GoogleHTTPClient(access_token=gmail_token or shared_token))
    if calendar_token or shared_token:
        calendar = GoogleCalendarHTTPProvider(GoogleHTTPClient(access_token=calendar_token or shared_token))
    if gmail is None and calendar is None:
        return None
    return GoogleWorkspaceService(gmail=gmail, calendar=calendar)
