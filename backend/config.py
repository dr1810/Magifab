"""Configuration for the current upload-once movie pipeline only."""
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MagiFab Movie API"
    environment: str = "development"
    log_level: str = "INFO"
    api_version: str = "2.0.0"
    cors_origins: str = "*"
    movie_pipeline_dir: Path = Path("cache/movie-pipeline")
    movie_chunk_duration_seconds: int = Field(default=90, ge=30, le=300)
    movie_pipeline_retry_attempts: int = Field(default=3, ge=1, le=8)
    movie_pipeline_retry_base_seconds: float = Field(default=1.0, ge=0.1, le=30)
    books_dir: Path | None = Field(default=None, validation_alias=AliasChoices("BOOKS_DIR", "MAGIFAB_BOOKS_DIR"))
    dune_example_path: Path | None = Field(default=None, validation_alias=AliasChoices("DUNE_EXAMPLE_PATH", "MAGIFAB_DUNE_EXAMPLE_PATH"))
    dune_example_filename: str = Field(default="Frank Herbert - Dune 1 - Dune.pdf", validation_alias=AliasChoices("DUNE_EXAMPLE_FILENAME", "MAGIFAB_DUNE_EXAMPLE_FILENAME"))
    openai_api_key: SecretStr | None = Field(default=None, validation_alias=AliasChoices("OPENAI_API_KEY", "MAGIFAB_OPENAI_API_KEY"))
    openai_model: str = Field(default="gpt-5.6", validation_alias=AliasChoices("OPENAI_MODEL", "MAGIFAB_OPENAI_MODEL"))
    openai_max_output_tokens: int = Field(default=1_200, ge=300)
    gemini_api_key: SecretStr | None = Field(default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "MAGIFAB_GEMINI_API_KEY"))
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias=AliasChoices("GEMINI_MODEL", "MAGIFAB_GEMINI_MODEL"))

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MAGIFAB_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
