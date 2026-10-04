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
    telegram_polling_enabled: bool = False
    telegram_production_send: bool = False
    telegram_dry_run: bool = True

    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_editorial_model: str = "deepseek-flash"

    editorial_enabled: bool = False
    editorial_owner_user_id: str | None = None
    editorial_owner_chat_id: str | None = None
    editorial_channel_id: str | None = None
    editorial_db_path: str = ".jafar/editorial.sqlite3"
    editorial_auto_publish_green: bool = False
    editorial_image_model: str = "gpt-image-2.5-flare"
    editorial_image_size: str = "1024x1536"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
