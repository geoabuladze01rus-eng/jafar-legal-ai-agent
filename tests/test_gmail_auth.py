from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest
from google.oauth2.credentials import Credentials

from jafar.gmail_auth import (
    GMAIL_READONLY_SCOPE,
    GmailCredentialManager,
    GmailReauthorizationRequired,
    GmailSetupRequired,
    authorize_gmail_desktop_app,
)


class InMemoryCredentialStore:
    def __init__(self, value: str | None = None) -> None:
        self.value = value

    def load(self) -> str | None:
        return self.value

    def save(self, serialized_credentials: str) -> None:
        self.value = serialized_credentials

    def delete(self) -> None:
        self.value = None


def _valid_credentials_json() -> str:
    credentials = Credentials(
        token="synthetic-access-token",
        refresh_token="synthetic-refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="synthetic-desktop-client",
        client_secret="synthetic-desktop-secret",
        scopes=[GMAIL_READONLY_SCOPE],
    )
    credentials.expiry = datetime.now(UTC) + timedelta(hours=1)
    return credentials.to_json()


def test_missing_keychain_entry_stops_at_safe_setup_gate() -> None:
    manager = GmailCredentialManager(InMemoryCredentialStore())

    with pytest.raises(GmailSetupRequired):
        manager.load_valid_credentials()


def test_credential_manager_accepts_only_exact_readonly_scope() -> None:
    manager = GmailCredentialManager(InMemoryCredentialStore(_valid_credentials_json()))

    credentials = manager.load_valid_credentials()

    assert credentials.valid is True
    assert set(credentials.scopes or ()) == {GMAIL_READONLY_SCOPE}


def test_credential_manager_rejects_broader_gmail_scope_before_use() -> None:
    payload = json.loads(_valid_credentials_json())
    payload["scopes"] = [GMAIL_READONLY_SCOPE, "https://www.googleapis.com/auth/gmail.modify"]
    manager = GmailCredentialManager(InMemoryCredentialStore(json.dumps(payload)))

    with pytest.raises(GmailReauthorizationRequired):
        manager.load_valid_credentials()


def test_installed_app_setup_requests_readonly_and_saves_to_store(monkeypatch, tmp_path) -> None:
    secrets_file = tmp_path / "desktop-client.json"
    secrets_file.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "synthetic-desktop-client",
                    "client_secret": "synthetic-desktop-secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
        ),
        encoding="utf-8",
    )
    calls: dict[str, object] = {}

    class FakeCredentials:
        granted_scopes: ClassVar[list[str]] = [GMAIL_READONLY_SCOPE]
        scopes: ClassVar[list[str]] = [GMAIL_READONLY_SCOPE]
        refresh_token = "synthetic-refresh-token"

        @staticmethod
        def to_json() -> str:
            return json.dumps({"scopes": [GMAIL_READONLY_SCOPE], "type": "synthetic"})

    class FakeFlow:
        def run_local_server(self, **kwargs):
            calls["run"] = kwargs
            return FakeCredentials()

    def fake_from_file(path: str, *, scopes: list[str]):
        calls["path"] = path
        calls["scopes"] = scopes
        return FakeFlow()

    monkeypatch.setattr(
        "jafar.gmail_auth.InstalledAppFlow.from_client_secrets_file",
        fake_from_file,
    )
    store = InMemoryCredentialStore()

    authorize_gmail_desktop_app(secrets_file, store)

    assert calls["scopes"] == [GMAIL_READONLY_SCOPE]
    assert calls["run"]["host"] == "127.0.0.1"
    assert calls["run"]["access_type"] == "offline"
    assert json.loads(store.value or "{}")["scopes"] == [GMAIL_READONLY_SCOPE]


def test_setup_rejects_web_oauth_client_before_opening_browser(tmp_path) -> None:
    secrets_file = tmp_path / "web-client.json"
    secrets_file.write_text(json.dumps({"web": {"client_id": "synthetic"}}), encoding="utf-8")

    with pytest.raises(GmailSetupRequired, match="Desktop app"):
        authorize_gmail_desktop_app(secrets_file, InMemoryCredentialStore())
