import os

from pydantic_settings import BaseSettings, SettingsConfigDict


def is_desktop_runtime() -> bool:
    """Whether this process is the bundled, local-only macOS sidecar."""

    return os.getenv("JAFAR_RUNTIME_MODE", "").strip().lower() == "desktop"


class Settings(BaseSettings):
    app_name: str = "Jafar Legal AI Agent"
    environment: str = "development"
    log_level: str = "INFO"
    api_key: str | None = None
    openai_api_key: str | None = None
    model_provider: str = "openai"
    model_name: str = "gpt-5.6"

    ollama_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout_seconds: float = 120.0
    ollama_health_timeout_seconds: float = 0.35
    ollama_keep_alive: str = "5m"
    ollama_think: bool = False
    confidential_cloud_fallback: bool = False

    telegram_bot_token: str | None = None
    telegram_polling_enabled: bool = False
    telegram_production_send: bool = False
    telegram_dry_run: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# A packaged sidecar gets its deliberately small configuration from its supervisor.
# In particular it must never discover a developer's working-directory .env file.
settings = Settings(_env_file=None if is_desktop_runtime() else ".env")
