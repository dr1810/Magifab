"""Request and response schemas for retrieval-first knowledge expansion."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.fusion import UnifiedSceneRepresentation
from schemas.knowledge import KnowledgeRecord, SceneSummary


class KnowledgeExpansionRequest(BaseModel):
    """Image is required only on a knowledge miss; a cache hit returns without decoding it."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str = Field(min_length=1)
    scene_id: str | None = None
    timestamp_seconds: float = Field(ge=0)
    image: str | None = Field(default=None, min_length=8)

    @field_validator("image")
    @classmethod
    def normalize_image(cls, value: str | None) -> str | None:
        return value.strip() if value else None


class KnowledgeExpansionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["retrieved", "expanded"]
    cache_key: str
    record: KnowledgeRecord
    scene_summary: SceneSummary | None = None
    perception: UnifiedSceneRepresentation | None = None
