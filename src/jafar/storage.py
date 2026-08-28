from __future__ import annotations

from enum import StrEnum

from .config import Settings
from .matter_repository import MatterRepository
from .matters import MatterStore
from .supabase_config import SupabaseSettings, build_supabase_client
from .supabase_matter_repository import SupabaseMatterRepository


class StorageBackend(StrEnum):
    MEMORY = "memory"
    SUPABASE = "supabase"


def storage_backend(settings: Settings) -> StorageBackend:
    try:
        return StorageBackend(settings.storage_backend.strip().casefold())
    except ValueError as exc:
        raise RuntimeError(
            f"Unsupported STORAGE_BACKEND: {settings.storage_backend!r}"
        ) from exc


def validate_storage_security(settings: Settings) -> None:
    backend = storage_backend(settings)
    if settings.environment.strip().casefold() == "production" and backend is StorageBackend.MEMORY:
        raise RuntimeError(
            "Production requires persistent STORAGE_BACKEND=supabase; memory storage is ephemeral"
        )


def build_matter_repository(settings: Settings) -> MatterRepository:
    backend = storage_backend(settings)
    if backend is StorageBackend.MEMORY:
        return MatterStore()

    supabase_settings = SupabaseSettings()
    owner_user_id = supabase_settings.require_owner_user_id()
    client = build_supabase_client(supabase_settings, server=True)
    return SupabaseMatterRepository(
        client,
        owner_user_id,
        server_mode=True,
    )
