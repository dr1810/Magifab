"""Stable, model-independent schemas for the perception fusion layer."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.detection import DetectionResponse
from schemas.understanding import UnderstandingResponse

EntityCategory = Literal["person", "animal", "object", "unknown"]


class UnifiedEntity(BaseModel):
    """A visible entity, never a movie-character identity."""
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1)
    category: EntityCategory
    bounding_box: list[float] | None = Field(default=None, min_length=4, max_length=4)
    confidence: float | None = Field(default=None, ge=0, le=1)
    sources: list[str] = Field(min_length=1)
    visual_attributes: dict[str, list[str]] = Field(default_factory=dict)


class PerceptionContribution(BaseModel):
    """Normalized evidence produced by one perception provider or adapter."""
    model_config = ConfigDict(extra="forbid")
    provider: str
    scene_description: str = ""
    entities: list[UnifiedEntity] = Field(default_factory=list)
    environment: str = ""
    actions: list[str] = Field(default_factory=list)
    interactions: list[str] = Field(default_factory=list)
    visual_attributes: dict[str, list[str]] = Field(default_factory=dict)


class UnifiedSceneRepresentation(BaseModel):
    """All current-frame perception evidence in one downstream-safe representation."""
    model_config = ConfigDict(extra="forbid")
    scene_description: str = ""
    entities: list[UnifiedEntity] = Field(default_factory=list)
    people: list[UnifiedEntity] = Field(default_factory=list)
    animals: list[UnifiedEntity] = Field(default_factory=list)
    objects: list[UnifiedEntity] = Field(default_factory=list)
    environment: str = ""
    actions: list[str] = Field(default_factory=list)
    interactions: list[str] = Field(default_factory=list)
    visual_attributes: dict[str, list[str]] = Field(default_factory=dict)
    providers: list[str] = Field(default_factory=list)


class FusionRequest(BaseModel):
    """Existing perception responses to fuse; no image or model inference is performed."""
    model_config = ConfigDict(extra="forbid")
    object_detection: DetectionResponse
    scene_understanding: UnderstandingResponse
