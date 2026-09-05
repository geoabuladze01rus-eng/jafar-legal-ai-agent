from __future__ import annotations

import pytest

from jafar.google_oauth_api import resolve_google_oauth_subject


def test_development_oauth_subject_can_come_from_authenticated_caller(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("JAFAR_GOOGLE_OAUTH_SUBJECT", raising=False)
    monkeypatch.delenv("JAFAR_LEGAL_RESEARCH_OWNER_USER_ID", raising=False)

    assert resolve_google_oauth_subject("local-user") == "local-user"


def test_protected_environment_oauth_subject_is_server_bound(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JAFAR_GOOGLE_OAUTH_SUBJECT", "deployment-owner")

    assert resolve_google_oauth_subject("caller-controlled") == "deployment-owner"


def test_protected_environment_fails_closed_without_oauth_subject(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.delenv("JAFAR_GOOGLE_OAUTH_SUBJECT", raising=False)
    monkeypatch.delenv("JAFAR_LEGAL_RESEARCH_OWNER_USER_ID", raising=False)

    with pytest.raises(RuntimeError, match="fixed Google OAuth subject"):
        resolve_google_oauth_subject("caller-controlled")
