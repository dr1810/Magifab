"""Typed state for the companion's temporal, LSTM-like movie memory."""
from pydantic import BaseModel, ConfigDict, Field


class CapturedFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp_seconds: float = Field(ge=0)
    frame_hash: str | None = None


class SlidingWindow(BaseModel):
    """A bounded semantic observation, rather than an isolated screenshot."""
    model_config = ConfigDict(extra="forbid")
    start_timestamp: float = Field(ge=0)
    end_timestamp: float = Field(ge=0)
    captured_frames: list[CapturedFrame] = Field(default_factory=list)
    detected_characters: list[str] = Field(default_factory=list)
    detected_objects: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    emotions: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)


class ShortTermMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_window: SlidingWindow | None = None
    recent_actions: list[str] = Field(default_factory=list)
    conversation_context: list[str] = Field(default_factory=list)


class LongTermMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    known_characters: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    important_events: list[str] = Field(default_factory=list)
    timeline: list[str] = Field(default_factory=list)
    emotional_arc: list[str] = Field(default_factory=list)


class AttentionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: str = Field(min_length=1)
    importance_score: float = Field(ge=0)
    character_change: float = Field(ge=0)
    relationship_change: float = Field(ge=0)
    plot_relevance: float = Field(ge=0)
    emotional_change: float = Field(ge=0)


class TemporalMemoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    window: SlidingWindow
    short_term: ShortTermMemory
    long_term: LongTermMemory
    new_characters: list[str] = Field(default_factory=list)
    new_events: list[str] = Field(default_factory=list)
    attention_events: list[AttentionEvent] = Field(default_factory=list)
    selected_claim_ids: list[str] = Field(default_factory=list)

