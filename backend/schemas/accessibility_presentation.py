"""Canonical UI contract: accessibility guidance, never perception or graph data."""
from pydantic import BaseModel, ConfigDict, Field

from schemas.accessibility_reasoning import (
    CharacterCard,
    ConversationSimplification,
    EmotionSummary,
    MemoryReminder,
    PromptBubbleSuggestion,
    RelationshipSummary,
    TimelineSummary,
    VocabularyAssistance,
)


class AccessibilityPresentation(BaseModel):
    """The only domain payload sent to viewer clients during normal operation."""
    model_config = ConfigDict(extra="forbid")
    scene_explanation: str
    prompt_bubbles: list[PromptBubbleSuggestion] = Field(default_factory=list)
    character_cards: list[CharacterCard] = Field(default_factory=list)
    relationship_summaries: list[RelationshipSummary] = Field(default_factory=list)
    timeline_summary: TimelineSummary | None = None
    emotion_summaries: list[EmotionSummary] = Field(default_factory=list)
    vocabulary_assistance: list[VocabularyAssistance] = Field(default_factory=list)
    memory_reminders: list[MemoryReminder] = Field(default_factory=list)
    conversation_simplifications: list[ConversationSimplification] = Field(default_factory=list)
