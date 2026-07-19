"""The immutable, complete client snapshot for one narrative interval.

This is the public boundary of the companion backend.  All screen-level
projections are fields of this snapshot; no sibling response payload is
allowed to carry another version of the same story information.
"""
from pydantic import BaseModel, ConfigDict, Field

from schemas.accessibility_reasoning import (
    CharacterCard, ConversationSimplification, EmotionSummary, MemoryReminder,
    PromptBubbleSuggestion, RelationshipSummary, VocabularyAssistance,
)
from schemas.presented_story_state import PresentedCauseEffect, PresentedCharacter


class ImmutableModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IntervalMetadata(ImmutableModel):
    interval_id: str
    # Catalog scenes are optional enrichment labels only.  Interval bounds are
    # the runtime identity used by playback, memory, and cache retrieval.
    catalog_scene_id: str | None = None
    movie_id: str
    start_time: float = Field(ge=0)
    end_time: float | None = Field(default=None, ge=0)
    interval_number: int = Field(ge=0)
    knowledge_revision: int = Field(ge=1)


class PromptAnswer(ImmutableModel):
    prompt_id: str
    question: str
    answer: str


class IntervalPrompts(ImmutableModel):
    prompt_bubbles: tuple[PromptBubbleSuggestion, ...] = ()
    prompt_answers: tuple[PromptAnswer, ...] = ()
    suggested_questions: tuple[str, ...] = ()


class VisualDrawerState(ImmutableModel):
    story_now: tuple[str, ...] = ()
    relationships: tuple[str, ...] = ()
    timeline: tuple[str, ...] = ()
    emotion: str | None = None
    cause_effect: tuple[PresentedCauseEffect, ...] = ()
    objects: tuple[str, ...] = ()
    memory: tuple[str, ...] = ()


class IntervalStoryState(ImmutableModel):
    scene_summary: str | None = None
    current_goal: str
    current_interval_id: str | None = None
    timeline_position: str | None = None
    story_so_far: tuple[str, ...] = ()
    unresolved_threads: tuple[str, ...] = ()


class ConversationContext(ImmutableModel):
    scene_explanation: str
    simplifications: tuple[ConversationSimplification, ...] = ()


class AccessibilityHints(ImmutableModel):
    vocabulary: tuple[VocabularyAssistance, ...] = ()
    emotions: tuple[EmotionSummary, ...] = ()


class IntervalSemanticMemory(ImmutableModel):
    """A frozen semantic-memory checkpoint on either side of an interval."""
    active_characters: tuple[str, ...] = ()
    relationships: tuple[str, ...] = ()
    emotions: tuple[str, ...] = ()
    important_objects: tuple[str, ...] = ()
    unresolved_threads: tuple[str, ...] = ()
    story_events: tuple[str, ...] = ()


class IntervalCacheMetadata(ImmutableModel):
    semantic_cache_key: str
    knowledge_source: str
    semantic_map_cached: bool
    frame_hash: str | None = None


class IntervalState(ImmutableModel):
    """Single source of truth sent to the frontend for one interval."""
    metadata: IntervalMetadata
    prompts: IntervalPrompts = Field(default_factory=IntervalPrompts)
    visualDrawer: VisualDrawerState = Field(default_factory=VisualDrawerState)
    storyState: IntervalStoryState
    characters: tuple[CharacterCard, ...] = ()
    relationships: tuple[RelationshipSummary, ...] = ()
    memory: tuple[MemoryReminder, ...] = ()
    conversationContext: ConversationContext
    accessibilityHints: AccessibilityHints = Field(default_factory=AccessibilityHints)
    semanticMemoryBefore: IntervalSemanticMemory
    semanticMemoryAfter: IntervalSemanticMemory
    cacheMetadata: IntervalCacheMetadata
