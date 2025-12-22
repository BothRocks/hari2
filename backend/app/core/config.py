# backend/app/core/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "HARI"
    environment: str = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://localhost:5432/hari2"

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    admin_api_key: str = "dev-admin-key"

    # LLM Providers
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    # Google OAuth
    google_client_id: str | None = None
    google_client_secret: str | None = None

    # Optional services
    jina_api_key: str | None = None
    tavily_api_key: str | None = None

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
