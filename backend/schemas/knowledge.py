"""Versioned semantic movie knowledge records used by matching and retrieval."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SemanticCharacter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    perception_labels: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)


class SemanticLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)


class SemanticObject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    perception_labels: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)


class SemanticRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    from_character_id: str = Field(min_length=1)
    to_character_id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class TimelinePosition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    description: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> "TimelinePosition":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be greater than or equal to start_seconds")
        return self


class SemanticEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence_terms: list[str] = Field(min_length=1)
    timeline_position_id: str | None = None


class DialogueSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str = Field(min_length=1)
    speaker_character_id: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)

    @model_validator(mode="after")
    def validate_range(self) -> "DialogueSegment":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be greater than or equal to start_seconds")
        return self


class VisibleSceneEntity(BaseModel):
    """Perception evidence bound to one scene; a semantic_id is present only after verification."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    category: str = Field(min_length=1)
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    confidence: float = Field(ge=0, le=1)
    sources: list[str] = Field(default_factory=list)
    semantic_id: str | None = None


class SceneSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_id: str = Field(min_length=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    summary: str = Field(min_length=1)
    confidence: float = Field(default=1.0, ge=0, le=1)
    visible_entities: list[VisibleSceneEntity] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    interactions: list[str] = Field(default_factory=list)
    environment: str = ""
    potential_confusions: list[str] = Field(default_factory=list)
    prepared: bool = False

    @model_validator(mode="after")
    def validate_range(self) -> "SceneSummary":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be greater than or equal to start_seconds")
        return self


class KnownAlias(BaseModel):
    model_config = ConfigDict(extra="forbid")
    semantic_id: str = Field(min_length=1)
    alias: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    confidence: float = Field(default=1.0, ge=0, le=1)


class VisualAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    semantic_id: str | None = None
    scene_id: str | None = None
    timestamp_seconds: float = Field(ge=0)
    bbox: list[float] = Field(min_length=4, max_length=4)
    confidence: float = Field(ge=0, le=1)


class FaceReference(BaseModel):
    """An enrolled embedding for verification against a known Semantic Movie Knowledge character."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    character_id: str = Field(min_length=1)
    embedding: list[float] = Field(min_length=1)
    model: str = Field(min_length=1)
    confidence: float = Field(default=1.0, ge=0, le=1)


class ObservationHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    timestamp_seconds: float = Field(ge=0)
    entity_label: str = Field(min_length=1)
    semantic_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    source: str = Field(min_length=1)


class EmotionFact(BaseModel):
    """A verified emotion supplied by movie knowledge, never inferred by accessibility reasoning."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    scene_id: str | None = None
    character_id: str | None = None
    emotion: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    confidence: float = Field(default=1.0, ge=0, le=1)


class VocabularyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    term: str = Field(min_length=1)
    simple_definition: str = Field(min_length=1)
    scene_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)


class SemanticMovieKnowledge(BaseModel):
    """Versioned, structured movie knowledge; no automatic enrichment occurs here."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str = Field(min_length=1)
    version: int = Field(default=1, ge=1)
    confidence: float = Field(default=1.0, ge=0, le=1)
    characters: list[SemanticCharacter] = Field(default_factory=list)
    locations: list[SemanticLocation] = Field(default_factory=list)
    objects: list[SemanticObject] = Field(default_factory=list)
    relationships: list[SemanticRelationship] = Field(default_factory=list)
    events: list[SemanticEvent] = Field(default_factory=list)
    timeline_positions: list[TimelinePosition] = Field(default_factory=list)
    dialogue: list[DialogueSegment] = Field(default_factory=list)
    scene_summaries: list[SceneSummary] = Field(default_factory=list)
    known_aliases: list[KnownAlias] = Field(default_factory=list)
    visual_anchors: list[VisualAnchor] = Field(default_factory=list)
    face_references: list[FaceReference] = Field(default_factory=list)
    observation_history: list[ObservationHistoryItem] = Field(default_factory=list)
    emotions: list[EmotionFact] = Field(default_factory=list)
    vocabulary: list[VocabularyEntry] = Field(default_factory=list)


class KnowledgeRecord(BaseModel):
    """Persisted envelope with immutable creation time and monotonic revision metadata."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    knowledge: SemanticMovieKnowledge


class KnowledgeRetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    movie_id: str = Field(min_length=1)
    scene_id: str | None = None
    timestamp_seconds: float | None = Field(default=None, ge=0)


class KnowledgeRetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    found: bool
    record: KnowledgeRecord | None = None
    scene_summary: SceneSummary | None = None
    timeline_position: TimelinePosition | None = None
