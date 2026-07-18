"""Structured, deterministic accessibility-reasoning inputs and outputs."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.knowledge import VisualAnchor
from schemas.profiles import AccessibilityProfile, CompanionProfile
from schemas.reasoning_context import ReasoningContext

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
    claim_ids: list[str] = Field(default_factory=list)


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


class AccessibilityReasoningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: ReasoningContext
    companion_profile: CompanionProfile


class AccessibilityReasoningResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    companion_tone: str
    scene_summary: str
    likely_confusions: list[ConfusionPrediction] = Field(default_factory=list)
    prompt_bubbles: list[PromptBubbleSuggestion] = Field(default_factory=list)
    drawer: AccessibilityDrawerContent
