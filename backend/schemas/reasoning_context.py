"""The graph-only input contract for accessibility reasoning."""
from pydantic import BaseModel, ConfigDict, Field

from schemas.knowledge import SemanticRelationship, TimelinePosition
from schemas.profiles import AccessibilityProfile
from schemas.semantic_graph import SemanticClaim


class ReasoningEntity(BaseModel):
    """A named semantic entity active in the retrieved movie context."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(min_length=1)


class ContextRelationship(BaseModel):
    """A graph relationship selected for the current semantic scene."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(min_length=1)


class PreviousExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_ids: list[str] = Field(min_length=1)
    summary: str = Field(min_length=1)


class UnresolvedQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1)
    related_claim_ids: list[str] = Field(default_factory=list)


class ReasoningContext(BaseModel):
    """Only semantic claims and graph entities may cross into the reasoner."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    timestamp_seconds: float = Field(ge=0)
    accessibility_profile: AccessibilityProfile
    semantic_scene: list[SemanticClaim] = Field(default_factory=list)
    active_characters: list[ReasoningEntity] = Field(default_factory=list)
    active_objects: list[ReasoningEntity] = Field(default_factory=list)
    timeline: TimelinePosition | None = None
    timeline_claim_ids: list[str] = Field(default_factory=list)
    relationships: list[ContextRelationship] = Field(default_factory=list)
    previous_events: list[SemanticClaim] = Field(default_factory=list)
    previous_character_presence: list[SemanticClaim] = Field(default_factory=list)
    emotion_claims: list[SemanticClaim] = Field(default_factory=list)
    vocabulary_claims: list[SemanticClaim] = Field(default_factory=list)
    conversation_claims: list[SemanticClaim] = Field(default_factory=list)
    previous_explanations: list[PreviousExplanation] = Field(default_factory=list)
    unresolved_questions: list[UnresolvedQuestion] = Field(default_factory=list)
    # Semantic-only projection of durable movie memory for accessibility.
    live_story: dict[str, object] = Field(default_factory=dict)
