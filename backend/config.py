"""Environment-backed configuration; model choices never leak into business services."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MagiFab Semantic Scene Understanding"
    environment: str = "development"
    log_level: str = "INFO"
    api_version: str = "1.0.0"
    cors_origins: str = "*"
    yolo_model_id: str = "yolo11n.pt"
    yolo_device: str = "auto"
    detection_confidence_threshold: float = 0.35
    florence_model_id: str = "microsoft/Florence-2-base"
    florence_device: str = "auto"
    florence_max_new_tokens: int = 256
    max_image_bytes: int = 8_000_000
    max_image_dimension: int = 4_096

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MAGIFAB_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
