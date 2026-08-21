from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Jafar Legal AI Agent"
    environment: str = "development"
    log_level: str = "INFO"
    api_key: str | None = None
    model_provider: str = "openai"
    model_name: str = "gpt-5.6"
    telegram_bot_token: str | None = None
    telegram_webhook_secret: str | None = None
    telegram_webhook_url: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
