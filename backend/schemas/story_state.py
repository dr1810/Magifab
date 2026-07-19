"""Canonical, persistent story model used by all accessibility features."""
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StoryEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    entity_type: str


class StoryEvent(BaseModel):
    """The only unit permitted to advance story progression."""
    model_config = ConfigDict(extra="forbid")
    event_id: str
    timestamp_start: float = Field(ge=0)
    timestamp_end: float = Field(ge=0)
    importance_score: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    event_type: str
    semantic_claim_ids: list[str] = Field(default_factory=list)
    entities: list[StoryEntity] = Field(default_factory=list)
    summary: str
    is_new: bool
    requires_memory: bool
    requires_prompt: bool

    @model_validator(mode="after")
    def _valid_interval(self):
        if self.timestamp_start > self.timestamp_end:
            raise ValueError("StoryEvent timestamp_start must not exceed timestamp_end")
        return self


class CharacterState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    first_seen_timestamp: float = Field(ge=0)
    last_seen_timestamp: float = Field(ge=0)
    total_screen_time: float = Field(default=0, ge=0)
    current_visibility: bool = True
    associated_events: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)


class RelationshipState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    summary: str
    supporting_claim_ids: list[str] = Field(min_length=1)
    first_seen_timestamp: float = Field(ge=0)
    last_seen_timestamp: float = Field(ge=0)
    associated_events: list[str] = Field(default_factory=list)


class StoryState(BaseModel):
    """Single source of truth for one movie's evolving narrative state."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str
    known_characters: dict[str, CharacterState] = Field(default_factory=dict)
    known_relationships: dict[str, RelationshipState] = Field(default_factory=dict)
    known_locations: dict[str, StoryEntity] = Field(default_factory=dict)
    known_objects: dict[str, StoryEntity] = Field(default_factory=dict)
    current_scene: str | None = None
    current_timestamp: float = Field(default=0, ge=0)
    current_location: str | None = None
    current_goal: str | None = None
    active_emotions: dict[str, str] = Field(default_factory=dict)
    recent_events: list[StoryEvent] = Field(default_factory=list)
    story_so_far: list[StoryEvent] = Field(default_factory=list)
    open_story_threads: list[StoryEvent] = Field(default_factory=list)
    resolved_threads: list[StoryEvent] = Field(default_factory=list)
    memory_reminders: list[StoryEvent] = Field(default_factory=list)
    character_history: dict[str, list[StoryEvent]] = Field(default_factory=dict)
    relationship_history: dict[str, list[StoryEvent]] = Field(default_factory=dict)
    timeline_history: list[StoryEvent] = Field(default_factory=list)
    prompt_history: dict[str, float] = Field(default_factory=dict)


class StoryStateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: StoryState
    events: list[StoryEvent] = Field(default_factory=list)
