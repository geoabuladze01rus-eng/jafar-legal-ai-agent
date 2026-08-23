from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class SupabaseSettings(BaseSettings):
    """Runtime configuration; secrets must come from environment, never source control."""

    model_config = SettingsConfigDict(env_prefix="JAFAR_SUPABASE_", extra="ignore")

    url: str
    anon_key: str



def build_supabase_client(settings: SupabaseSettings):
    from supabase import create_client

    return create_client(settings.url, settings.anon_key)
