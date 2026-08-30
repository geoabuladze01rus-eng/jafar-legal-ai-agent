from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SupabaseSettings(BaseSettings):
    """Backend Supabase configuration loaded only from environment variables.

    The service-role key is a server secret and must never be embedded in Apple clients,
    browser bundles, logs, repository files, or API responses.
    """

    model_config = SettingsConfigDict(env_prefix="JAFAR_SUPABASE_", extra="ignore")

    url: str
    anon_key: SecretStr | None = None
    service_role_key: SecretStr | None = None
    owner_user_id: str | None = None

    def require_owner_user_id(self) -> str:
        owner = (self.owner_user_id or "").strip()
        if not owner:
            raise RuntimeError("JAFAR_SUPABASE_OWNER_USER_ID is required")
        return owner


def build_supabase_client(
    settings: SupabaseSettings,
    *,
    server: bool = False,
):
    from supabase import create_client

    secret = settings.service_role_key if server else settings.anon_key
    if secret is None:
        name = "JAFAR_SUPABASE_SERVICE_ROLE_KEY" if server else "JAFAR_SUPABASE_ANON_KEY"
        raise RuntimeError(f"{name} is required")
    return create_client(settings.url, secret.get_secret_value())
