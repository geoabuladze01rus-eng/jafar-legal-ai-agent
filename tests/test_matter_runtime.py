import pytest

import jafar.matter_runtime as matter_runtime
from jafar.matter_runtime import build_matter_repository_from_env
from jafar.matters import MatterStore
from jafar.supabase_matter_repository import SupabaseMatterRepository


def test_matter_runtime_falls_back_to_memory(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("JAFAR_SUPABASE_URL", raising=False)
    monkeypatch.delenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("JAFAR_LEGAL_RESEARCH_OWNER_USER_ID", raising=False)

    repository = build_matter_repository_from_env()

    assert isinstance(repository, MatterStore)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_matter_runtime_requires_persistent_storage_in_protected_environments(
    monkeypatch,
    environment: str,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.delenv("JAFAR_SUPABASE_URL", raising=False)
    monkeypatch.delenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("JAFAR_LEGAL_RESEARCH_OWNER_USER_ID", raising=False)

    with pytest.raises(RuntimeError, match="Persistent matter storage is required"):
        build_matter_repository_from_env()


def test_matter_runtime_uses_supabase_when_fully_configured(monkeypatch) -> None:
    client = object()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JAFAR_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", "synthetic-service-key")
    monkeypatch.setenv("JAFAR_LEGAL_RESEARCH_OWNER_USER_ID", "owner-test")
    monkeypatch.setattr(matter_runtime, "create_client", lambda *_: client)

    repository = build_matter_repository_from_env()

    assert isinstance(repository, SupabaseMatterRepository)
    assert repository.client is client
    assert repository.owner_user_id == "owner-test"
