"""Structured, deterministic accessibility-reasoning inputs and outputs."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.knowledge import SemanticMovieKnowledge, VisualAnchor


class AccessibilityProfile(BaseModel):
    """Backend representation of onboarding selections; terms remain intentionally extensible."""
    model_config = ConfigDict(extra="forbid")
    accessibility_needs: list[str] = Field(default_factory=list)
    detail_level: str = "brief"
    preferred_prompt_types: list[str] = Field(default_factory=list)
    conversation_simplification: bool = True
    vocabulary_assistance: bool = True


class CompanionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = "Companion"
    personality: str = "warm"
    conversation_style: str = "simple"


class CurrentScene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    character_ids: list[str] = Field(default_factory=list)
    object_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)


class ConfusionPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    confidence: float = Field(ge=0, le=1)
    reason: str


class PromptBubbleSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: str
    label: str
    question: str
    priority: int = Field(ge=1)


class CharacterCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    character_id: str
    name: str
    reminder: str
    confidence: float = Field(ge=0, le=1)
    visual_anchor: VisualAnchor | None = None


class RelationshipSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relationship_id: str
    summary: str
    confidence: float = Field(ge=0, le=1)


class TimelineSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    confidence: float = Field(ge=0, le=1)


class EmotionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    emotion_id: str
    summary: str
    confidence: float = Field(ge=0, le=1)


class MemoryReminder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    confidence: float = Field(ge=0, le=1)


class VocabularyAssistance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    term: str
    simple_definition: str
    confidence: float = Field(ge=0, le=1)


class ConversationSimplification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dialogue_id: str
    simple_text: str
    confidence: float = Field(ge=0, le=1)


class AccessibilityDrawerContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    character_cards: list[CharacterCard] = Field(default_factory=list)
    relationship_summaries: list[RelationshipSummary] = Field(default_factory=list)
    timeline_summary: TimelineSummary | None = None
    emotion_summaries: list[EmotionSummary] = Field(default_factory=list)
    memory_reminders: list[MemoryReminder] = Field(default_factory=list)
    vocabulary_assistance: list[VocabularyAssistance] = Field(default_factory=list)
    conversation_simplifications: list[ConversationSimplification] = Field(default_factory=list)


class AccessibilityReasoningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    knowledge: SemanticMovieKnowledge
    current_scene: CurrentScene
    timestamp_seconds: float = Field(ge=0)
    accessibility_profile: AccessibilityProfile
    companion_profile: CompanionProfile


class AccessibilityReasoningResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    companion_tone: str
    scene_summary: str
    likely_confusions: list[ConfusionPrediction] = Field(default_factory=list)
    prompt_bubbles: list[PromptBubbleSuggestion] = Field(default_factory=list)
    drawer: AccessibilityDrawerContent
