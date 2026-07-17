"""Environment-backed configuration for the Phase 1 HTTP foundation."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MagiFab Semantic Scene Understanding"
    environment: str = "development"
    log_level: str = "INFO"
    api_version: str = "1.0.0"
    cors_origins: str = "*"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MAGIFAB_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
