"""Structured, deterministic accessibility-reasoning inputs and outputs."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.knowledge import VisualAnchor
from schemas.profiles import AccessibilityProfile, CompanionProfile
from schemas.story_state import StoryState
from schemas.timeline_memory import TimelineState

class PromptBubbleSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
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
    model_config = ConfigDict(extra="forbid", frozen=True)
    character_id: str
    name: str
    reminder: str
    confidence: float = Field(ge=0, le=1)
    visual_anchor: VisualAnchor | None = None
    claim_ids: list[str] = Field(default_factory=list)


class RelationshipSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    relationship_id: str
    summary: str
    confidence: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(default_factory=list)


class EmotionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    emotion_id: str
    summary: str
    confidence: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(default_factory=list)


class MemoryReminder(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    summary: str
    confidence: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(default_factory=list)


class VocabularyAssistance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    term: str
    simple_definition: str
    confidence: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(default_factory=list)


class ConversationSimplification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    dialogue_id: str
    simple_text: str
    confidence: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(default_factory=list)


class AccessibilityReasoningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    story_state: StoryState
    timeline_state: TimelineState | None = None
    accessibility_profile: AccessibilityProfile
    companion_profile: CompanionProfile
