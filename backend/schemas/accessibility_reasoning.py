"""Structured, deterministic accessibility-reasoning inputs and outputs."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.knowledge import VisualAnchor
from schemas.profiles import AccessibilityProfile, CompanionProfile
from schemas.profiles import AccessibilityProfile
from schemas.story_state import StoryState
from schemas.timeline_memory import TimelineState

class PromptBubbleSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: str
    label: str
    question: str
    priority: int = Field(ge=1)
    claim_ids: list[str] = Field(default_factory=list)
    timestamp_start: float | None = Field(default=None, ge=0)
    timestamp_end: float | None = Field(default=None, ge=0)
    semantic_event: str | None = None
    screen_location: str = "bottom-right"


class CharacterCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    character_id: str
    name: str
    reminder: str
    confidence: float = Field(ge=0, le=1)
    visual_anchor: VisualAnchor | None = None
    claim_ids: list[str] = Field(default_factory=list)


class RelationshipSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relationship_id: str
    summary: str
    confidence: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(default_factory=list)


class TimelineSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    confidence: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(default_factory=list)


class EmotionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    emotion_id: str
    summary: str
    confidence: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(default_factory=list)


class MemoryReminder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    confidence: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(default_factory=list)


class VocabularyAssistance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    term: str
    simple_definition: str
    confidence: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(default_factory=list)


class ConversationSimplification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dialogue_id: str
    simple_text: str
    confidence: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(default_factory=list)


class AccessibilityDrawerContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    character_cards: list[CharacterCard] = Field(default_factory=list)
    relationship_summaries: list[RelationshipSummary] = Field(default_factory=list)
    timeline_summary: TimelineSummary | None = None
    emotion_summaries: list[EmotionSummary] = Field(default_factory=list)
    memory_reminders: list[MemoryReminder] = Field(default_factory=list)
    vocabulary_assistance: list[VocabularyAssistance] = Field(default_factory=list)
    conversation_simplifications: list[ConversationSimplification] = Field(default_factory=list)


class LiveStoryAssistant(BaseModel):
    """Timestamped persistent-memory snapshot for the visual drawer."""
    model_config = ConfigDict(extra="forbid")
    current_scene: str
    current_timestamp: float = Field(ge=0)
    current_goal: str | None = None
    current_characters: list[str] = Field(default_factory=list)
    current_emotions: list[str] = Field(default_factory=list)
    current_relationships: list[str] = Field(default_factory=list)
    recent_events: list[str] = Field(default_factory=list)
    timeline_position: str | None = None
    story_so_far: list[str] = Field(default_factory=list)
    important_objects: list[str] = Field(default_factory=list)
    memory_reminders: list[str] = Field(default_factory=list)
    unresolved_story_threads: list[str] = Field(default_factory=list)


class AccessibilityReasoningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    story_state: StoryState
    timeline_state: TimelineState | None = None
    accessibility_profile: AccessibilityProfile
    companion_profile: CompanionProfile
