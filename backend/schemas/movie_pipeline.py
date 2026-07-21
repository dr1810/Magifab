"""Public and provider-neutral contracts for durable movie preprocessing."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MovieProcessingStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ChunkProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    event: str = Field(min_length=1, max_length=2_000)


class VisualEntity(BaseModel):
    """An entity observed by Gemini. `Unknown` is a valid, valuable outcome."""
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=2_000)
    certainty: Confidence = Confidence.LOW
    emotion: str | None = Field(default=None, max_length=240)
    action: str | None = Field(default=None, max_length=1_000)


class EntityNeedingIdentification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity: str = Field(min_length=1, max_length=240)
    kind: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=2_000)
    reason: str = Field(min_length=1, max_length=1_000)
    certainty: Confidence = Confidence.LOW


class GeminiVisualScene(BaseModel):
    """Visual-only evidence. This must not contain accessibility interpretation."""
    model_config = ConfigDict(extra="forbid")
    scene_summary: str = Field(min_length=1, max_length=4_000)
    characters: list[VisualEntity] = Field(default_factory=list)
    objects: list[VisualEntity] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    emotions: list[str] = Field(default_factory=list)
    important_visual_cues: list[str] = Field(default_factory=list)
    difficulty_points: list[str] = Field(default_factory=list)
    important_memory: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    entities_needing_identification: list[EntityNeedingIdentification] = Field(default_factory=list)
    confidence: Confidence = Confidence.LOW


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="", max_length=1_000)
    snippet: str = Field(default="", max_length=4_000)
    url: str = Field(default="", max_length=4_000)
    confidence: float = Field(default=0.0, ge=0, le=1)


class SearchContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity: str = Field(min_length=1)
    entity_kind: str = Field(min_length=1)
    query: str = Field(min_length=1)
    results: list[SearchResult] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)


class CanonicalEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=2_000)
    confidence: Confidence = Confidence.LOW
    source: str = Field(min_length=1, max_length=80)


class CanonicalRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=240)
    relationship: str = Field(min_length=1, max_length=1_000)
    object: str = Field(min_length=1, max_length=240)
    confidence: Confidence = Confidence.LOW


class VisualAid(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=2_000)


class CauseEffect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cause: str = Field(min_length=1, max_length=2_000)
    effect: str = Field(min_length=1, max_length=2_000)


class CanonicalMagiFabScene(BaseModel):
    """The permanent frontend-facing representation for one video chunk."""
    model_config = ConfigDict(extra="forbid")
    scene_summary: str = Field(min_length=1, max_length=4_000)
    characters: list[CanonicalEntity] = Field(default_factory=list)
    relationships: list[CanonicalRelationship] = Field(default_factory=list)
    objects: list[CanonicalEntity] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    emotions: list[str] = Field(default_factory=list)
    cause_effect: list[CauseEffect] = Field(default_factory=list)
    important_memory: list[str] = Field(default_factory=list)
    difficulty_points: list[str] = Field(default_factory=list)
    visual_aid: VisualAid
    accessibility_explanation: str = Field(min_length=1, max_length=6_000)
    search_context: list[SearchContext] = Field(default_factory=list)
    confidence: Confidence = Confidence.LOW


class MovieRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    content_hash: str
    title: str | None = None
    original_filename: str
    mime_type: str
    source_storage_key: str = Field(exclude=True)
    status: MovieProcessingStatus
    model_versions: dict[str, str] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ChunkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    movie_id: str
    sequence_number: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    content_hash: str
    storage_key: str = Field(exclude=True)
    status: ChunkProcessingStatus
    model_versions: dict[str, str] = Field(default_factory=dict)
    gemini_visual_json: GeminiVisualScene | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class MovieUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    movie_id: str
    content_hash: str
    status: MovieProcessingStatus
    reused_existing: bool


class MoviePreprocessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    movie_id: str
    status: MovieProcessingStatus
    accepted: bool


class MovieProcessingStatusResponse(BaseModel):
    """Small, public status contract used by the loading screen.

    Internal database states deliberately do not leak into the player.  The
    player only needs to know where the one-time job is and whether it is safe
    to begin retrieval-only playback.
    """
    model_config = ConfigDict(extra="forbid")
    status: str
    progress: str
    percentage: int = Field(ge=0, le=100)
    error: str | None = None
    movie_id: str | None = None
    title: str | None = None


class CompanionProfilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    personality: str = "warm"
    accessibility_needs: list[str] = Field(default_factory=list)
    difficulties: list[str] = Field(default_factory=list)
    preferred_explanation_style: str = "simple"


class MoviePreprocessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    companion_profile: CompanionProfilePayload = Field(default_factory=CompanionProfilePayload)


class VisualDrawerArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    characters: list[dict[str, str]] = Field(default_factory=list)
    timeline: list[str] = Field(default_factory=list)
    objects: list[dict[str, str]] = Field(default_factory=list)
    memory: list[str] = Field(default_factory=list)
    emotion: list[str] = Field(default_factory=list)
    cause: list[dict[str, str]] = Field(default_factory=list)


class SceneArtifactResponse(BaseModel):
    """A stored artifact; this endpoint has no provider or preprocessing side effect."""
    model_config = ConfigDict(extra="forbid")
    timestamp: float
    promptBubble: list[dict[str, str]]
    companionExplanation: str
    visualDrawer: VisualDrawerArtifact
    visualAid: VisualAid
    characters: list[CanonicalEntity]
    memoryCue: list[str]


class MovieChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp: float = Field(ge=0)
    question: str = Field(min_length=1, max_length=4_000)
    companion_profile: CompanionProfilePayload = Field(default_factory=CompanionProfilePayload)


class CompanionChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    timestamp: float


class SceneRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    movie_id: str
    # Internal persistence key; browser clients only receive timestamp scene data.
    chunk_id: str = Field(exclude=True)
    canonical_scene: CanonicalMagiFabScene
    model_versions: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class SceneWindow(BaseModel):
    """Public timestamp range for caching an already-stored scene."""
    model_config = ConfigDict(extra="forbid")
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)


class SceneLookupResponse(BaseModel):
    """One stored scene selected by playback time; never triggers model work."""
    model_config = ConfigDict(extra="forbid")
    scene: SceneRecord | None = None
    scene_window: SceneWindow | None = None


JSON = dict[str, Any]
