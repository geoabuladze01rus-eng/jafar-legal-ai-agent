from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Jafar Legal AI Agent"
    environment: str = "development"
    log_level: str = "INFO"
    api_key: str | None = None
    openai_api_key: str | None = None
    model_provider: str = "openai"
    model_name: str = "gpt-5.6"

    google_oauth_enabled: bool = False
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str = "http://127.0.0.1:8000/v1/integrations/google/callback"
    google_oauth_prompt: str = "consent"
    google_oauth_scopes: str = (
        "openid email profile "
        "https://www.googleapis.com/auth/gmail.readonly "
        "https://www.googleapis.com/auth/drive.readonly "
        "https://www.googleapis.com/auth/calendar.readonly"
    )

    telegram_bot_token: str | None = None
    telegram_polling_enabled: bool = False
    telegram_production_send: bool = False
    telegram_dry_run: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
