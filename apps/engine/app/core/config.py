from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/regos"
    # Not used yet -- wired up when Phase 1 (extraction engine) starts.
    anthropic_api_key: Optional[str] = None


settings = Settings()
