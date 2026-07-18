"""End-to-end retrieval-first runtime request and response contracts."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.accessibility_reasoning import AccessibilityProfile, CompanionProfile
from schemas.accessibility_presentation import AccessibilityPresentation
from schemas.personalization import GPTPersonalizationResponse


class CompanionPipelineRequest(BaseModel):
    """Interaction requests retrieve prepared scene knowledge; they never carry an image."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str = Field(min_length=1)
    timestamp_seconds: float = Field(ge=0)
    scene_id: str | None = None
    scene_summary: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=2_000)
    intent: str = Field(default="general", min_length=1, max_length=100)
    image: str | None = Field(default=None, min_length=8)
    grounding_queries: list[str] = Field(default_factory=list, max_length=20)
    verify_faces: bool = False
    accessibility_profile: AccessibilityProfile
    companion_profile: CompanionProfile

    @field_validator("image")
    @classmethod
    def normalize_image(cls, value: str | None) -> str | None:
        return value.strip() if value else None


class CompanionPipelineResponse(BaseModel):
    """A personalized response plus the verified structured facts that produced it."""
    model_config = ConfigDict(extra="forbid")
    knowledge_source: Literal["retrieved", "expanded"]
    response_cache_hit: bool
    cache_key: str
    knowledge_revision: int = Field(ge=1)
    response: GPTPersonalizationResponse
    presentation: AccessibilityPresentation


class ScenePreparationRequest(BaseModel):
    """One representative frame for a scene, supplied before prompts are exposed."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    timestamp_seconds: float = Field(ge=0)
    scene_summary: str = Field(min_length=1)
    image: str = Field(min_length=8)
    # Optional caller hints supplement (never replace) the labels discovered by
    # YOLO. Keeping this on the preparation contract makes grounding extensible
    # for uploaded movies without coupling the UI to a particular model.
    grounding_queries: list[str] = Field(default_factory=list, max_length=20)
    verify_faces: bool = False
    accessibility_profile: AccessibilityProfile
    companion_profile: CompanionProfile


class PreparationCacheMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cache_key: str
    frame_hash: str | None = None
    knowledge_revision: int = Field(ge=1)
    knowledge_source: Literal["retrieved", "expanded"]
    semantic_map_cached: bool
    reasoning_cached: bool = True


class ScenePreparationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    knowledge_source: Literal["retrieved", "expanded"]
    knowledge_revision: int = Field(ge=1)
    presentation: AccessibilityPresentation
    cache: PreparationCacheMetadata
