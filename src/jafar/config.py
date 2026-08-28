from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Jafar Legal AI Agent"
    environment: str = "development"
    log_level: str = "INFO"
    api_key: str | None = None
    openai_api_key: str | None = None
    model_provider: str = "openai"
    model_name: str = "gpt-5.6"
    telegram_bot_token: str | None = None
    telegram_allowed_chat_ids: str = ""
    telegram_polling_enabled: bool = False
    telegram_production_send: bool = False
    telegram_dry_run: bool = True
    telegram_scheduler_db_path: str = "./data/telegram.sqlite3"
    telegram_scheduler_enabled: bool = False
    jafar_mcp_auth_token: str | None = None
    jafar_mcp_public_url: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
