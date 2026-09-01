from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from jafar.google_oauth import GoogleTokenSet, InMemoryGoogleTokenStore
from jafar.supabase_google_token_store import SupabaseGoogleTokenStore, build_google_token_store_from_env


class FakeQuery:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return SimpleNamespace(data=self.data)


class FakeSupabaseClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        if name == "load_google_oauth_token":
            return FakeQuery(
                [
                    {
                        "access_token": "access",
                        "refresh_token": "refresh",
                        "expires_at": "2026-08-31T12:00:00+00:00",
                        "scope": "scope",
                        "token_type": "Bearer",
                    }
                ]
            )
        return FakeQuery([])


def test_selects_persistent_store_when_all_supabase_settings_are_configured(monkeypatch):
    client = FakeSupabaseClient()
    monkeypatch.setenv("JAFAR_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setenv("JAFAR_GOOGLE_TOKEN_ENCRYPTION_KEY", "encryption-key")
    monkeypatch.setitem(
        __import__("sys").modules,
        "supabase",
        SimpleNamespace(create_client=lambda url, key: client),
    )

    store = build_google_token_store_from_env()

    assert isinstance(store, SupabaseGoogleTokenStore)
    assert store.client is client


def test_selects_in_memory_store_only_when_persistent_settings_are_incomplete(monkeypatch):
    monkeypatch.delenv("JAFAR_SUPABASE_URL", raising=False)
    monkeypatch.delenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("JAFAR_GOOGLE_TOKEN_ENCRYPTION_KEY", raising=False)

    assert isinstance(build_google_token_store_from_env(), InMemoryGoogleTokenStore)


def test_required_persistent_store_fails_closed_when_settings_are_incomplete(monkeypatch):
    monkeypatch.delenv("JAFAR_SUPABASE_URL", raising=False)
    monkeypatch.delenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("JAFAR_GOOGLE_TOKEN_ENCRYPTION_KEY", raising=False)

    with pytest.raises(RuntimeError, match="Persistent Google OAuth token storage"):
        build_google_token_store_from_env(require_persistent=True)


def test_supabase_store_round_trips_tokens_through_encrypted_rpc_contract():
    client = FakeSupabaseClient()
    store = SupabaseGoogleTokenStore(client, "encryption-key")
    token_set = GoogleTokenSet(
        access_token="access",
        refresh_token="refresh",
        expires_at=datetime(2026, 8, 31, 12, tzinfo=timezone.utc),
        scope="scope",
    )

    store.save("subject-1", token_set)
    loaded = store.load("subject-1")

    assert loaded is not None
    assert loaded.access_token == "access"
    assert [name for name, _ in client.calls] == ["upsert_google_oauth_token", "load_google_oauth_token"]
