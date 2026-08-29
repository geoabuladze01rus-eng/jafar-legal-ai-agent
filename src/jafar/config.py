from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Jafar Legal AI Agent"
    environment: str = "development"
    log_level: str = "INFO"
    api_key: str | None = None
    storage_backend: str = "memory"
    lawyer_approver_id: str | None = None
    openai_api_key: str | None = None
    model_provider: str = "openai"
    model_name: str = "gpt-5.6"
    ai_cost_control_enabled: bool = False
    ai_pricing_json: str | None = None
    ai_pricing_version: str | None = None
    ai_cost_per_request_usd: Decimal | None = None
    ai_cost_user_daily_usd: Decimal | None = None
    ai_cost_user_monthly_usd: Decimal | None = None
    ai_cost_global_daily_usd: Decimal | None = None
    ai_queue_backend: str = "memory"
    ai_queue_max_size: int = 1000
    ai_queue_max_per_user: int = 20
    ai_queue_worker_claim_limit: int = 5
    ai_rate_limit_requests: int = 30
    ai_rate_limit_window_seconds: int = 60
    telegram_bot_token: str | None = None
    telegram_allowed_chat_ids: str = ""
    telegram_polling_enabled: bool = False
    telegram_scheduler_enabled: bool = False
    telegram_scheduler_db_path: str = "var/telegram_scheduler.sqlite3"
    telegram_poll_identity_secret: str | None = None
    telegram_production_send: bool = False
    telegram_dry_run: bool = True
    jafar_mcp_auth_token: str | None = None
    jafar_mcp_public_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
