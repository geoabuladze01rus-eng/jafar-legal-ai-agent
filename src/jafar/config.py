from pydantic_settings import BaseSettings, SettingsConfigDict


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
    telegram_allowed_chat_ids: str = ""
    telegram_polling_enabled: bool = False
    telegram_scheduler_enabled: bool = False
    telegram_scheduler_db_path: str = "var/telegram_scheduler.sqlite3"
    telegram_scheduler_claim_timeout_seconds: int = 120
    telegram_max_video_bytes: int = 20 * 1024 * 1024
    telegram_poll_identity_secret: str | None = None
    telegram_production_send: bool = False
    telegram_dry_run: bool = True
    telegram_editorial_mode: str = "APPROVE"
    telegram_owner_approver_id: str | None = None
    telegram_egress_enabled: bool = False
    telegram_egress_url: str | None = None
    telegram_egress_auth_token: str | None = None

    jafar_mcp_auth_token: str | None = None
    jafar_mcp_public_url: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
