"""Timestamp-addressable semantic memory for playback and seeking.

Intervals are created by story changes, never by fixed perception windows.
"""
from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.story_state import StoryState


class TimelinePrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt_id: str
    start_timestamp: float = Field(ge=0)
    end_timestamp: float | None = Field(default=None, ge=0)
    priority: int = Field(ge=1)
    activation_reason: str
    semantic_event_id: str
    claim_ids: list[str] = Field(default_factory=list)
    label: str
    question: str
    kind: str

    @model_validator(mode="after")
    def _valid_lifetime(self):
        if self.end_timestamp is not None and self.end_timestamp < self.start_timestamp:
            raise ValueError("TimelinePrompt end_timestamp must not precede start_timestamp")
        return self


class TimelineDrawerState(BaseModel):
    """Stored drawer projection. Rendering never rebuilds this from claims."""
    model_config = ConfigDict(extra="forbid")
    start_timestamp: float = Field(ge=0)
    end_timestamp: float | None = Field(default=None, ge=0)
    story_so_far: list[str] = Field(default_factory=list)
    current_characters: list[str] = Field(default_factory=list)
    current_emotions: list[str] = Field(default_factory=list)
    current_relationships: list[str] = Field(default_factory=list)
    current_objects: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    important_memories: list[str] = Field(default_factory=list)


class TimelineState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp: float = Field(ge=0)
    story_state: StoryState
    prompts: list[TimelinePrompt] = Field(default_factory=list)
    drawer_state: TimelineDrawerState


class TimelineInterval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interval_id: str
    start_timestamp: float = Field(ge=0)
    end_timestamp: float | None = Field(default=None, ge=0)
    triggering_event_ids: list[str] = Field(min_length=1)
    importance: float = Field(ge=0)
    story_state_before: StoryState
    story_state_after: StoryState
    state: TimelineState

    @model_validator(mode="after")
    def _valid_interval(self):
        if self.end_timestamp is not None and self.end_timestamp < self.start_timestamp:
            raise ValueError("TimelineInterval end_timestamp must not precede start_timestamp")
        return self


class TimelineMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    movie_id: str
    intervals: list[TimelineInterval] = Field(default_factory=list)
