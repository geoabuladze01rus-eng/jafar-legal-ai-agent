import pytest

from jafar.config import Settings
from jafar.matters import MatterStore
from jafar.storage import (
    StorageBackend,
    build_matter_repository,
    storage_backend,
    validate_storage_security,
)
from jafar.supabase_matter_repository import SupabaseMatterRepository


def config(**overrides) -> Settings:
    values = {
        "environment": "development",
        "storage_backend": "memory",
        "api_key": None,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_development_defaults_to_in_memory_repository() -> None:
    settings = config()

    assert storage_backend(settings) is StorageBackend.MEMORY
    assert isinstance(build_matter_repository(settings), MatterStore)


def test_production_rejects_ephemeral_memory_storage() -> None:
    settings = config(environment="production", storage_backend="memory")

    with pytest.raises(RuntimeError, match="persistent STORAGE_BACKEND=supabase"):
        validate_storage_security(settings)


def test_unknown_storage_backend_is_rejected() -> None:
    settings = config(storage_backend="filesystem-maybe")

    with pytest.raises(RuntimeError, match="Unsupported STORAGE_BACKEND"):
        build_matter_repository(settings)


def test_supabase_factory_uses_server_mode_and_owner_scope(monkeypatch) -> None:
    settings = config(storage_backend="supabase")
    fake_client = object()

    class FakeSupabaseSettings:
        def require_owner_user_id(self) -> str:
            return "owner-123"

    monkeypatch.setattr("jafar.storage.SupabaseSettings", FakeSupabaseSettings)
    monkeypatch.setattr(
        "jafar.storage.build_supabase_client",
        lambda supplied, server: fake_client if server else None,
    )

    repository = build_matter_repository(settings)

    assert isinstance(repository, SupabaseMatterRepository)
    assert repository.client is fake_client
    assert repository.owner_user_id == "owner-123"
    assert repository.server_mode is True
