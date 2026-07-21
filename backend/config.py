"""Environment-backed configuration; model choices never leak into business services."""
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
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
    semantic_match_confidence_threshold: float = 0.8
    # A catalog participant is not automatically visible. This threshold gates
    # inferred presence before it can reach accessibility presentation.
    semantic_presence_confidence_threshold: float = Field(default=0.6, ge=0, le=1)
    semantic_prompt_cooldown_seconds: float = Field(default=8.0, ge=0)
    # Bump whenever prepared-scene output changes. Used in every cache key.
    # Version 21 keys prepared scene knowledge by movie/scene rather than a
    # one-off frame, and persists catalog emotion/timeline graph facts.
    semantic_cache_version: int = Field(default=21, ge=1)
    knowledge_store_dir: Path = Path("cache/movie-knowledge")
    # Uploaded video originals, chunk files, and the local preprocessing database.
    # Deployments may replace the file/SQLite implementation through the repository
    # and blob-storage contracts without changing the pipeline service.
    movie_pipeline_dir: Path = Path("cache/movie-pipeline")
    movie_chunk_duration_seconds: int = Field(default=90, ge=30, le=300)
    movie_pipeline_retry_attempts: int = Field(default=3, ge=1, le=8)
    movie_pipeline_retry_base_seconds: float = Field(default=1.0, ge=0.1, le=30)
    debug_frames_dir: Path = Path("debug_frames")
    openai_api_key: SecretStr | None = Field(default=None, validation_alias=AliasChoices("OPENAI_API_KEY", "MAGIFAB_OPENAI_API_KEY"))
    openai_model: str = Field(default="gpt-5.6", validation_alias=AliasChoices("OPENAI_MODEL", "MAGIFAB_OPENAI_MODEL"))
    openai_max_output_tokens: int = 300
    gemini_api_key: SecretStr | None = Field(default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "MAGIFAB_GEMINI_API_KEY"))
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias=AliasChoices("GEMINI_MODEL", "MAGIFAB_GEMINI_MODEL"))
    gemini_embedding_model: str = "gemini-embedding-2"
    debug_companion_pipeline: bool = False
    face_model_pack: str = "buffalo_l"
    face_onnx_providers: str = "CPUExecutionProvider"
    face_detection_size: int = 640
    face_verification_threshold: float = 0.6
    grounding_dino_model_id: str = "IDEA-Research/grounding-dino-tiny"
    grounding_dino_device: str = "auto"
    grounding_dino_box_threshold: float = 0.35
    grounding_dino_text_threshold: float = 0.25
    response_cache_max_entries: int = Field(default=500, ge=1)
    response_cache_timestamp_bucket_seconds: int = Field(default=5, ge=1)
    max_image_bytes: int = 8_000_000
    max_image_dimension: int = 4_096

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MAGIFAB_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
