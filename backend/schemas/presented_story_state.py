"""Clean, frontend-safe StoryState contract with no graph provenance."""
from pydantic import BaseModel, ConfigDict, Field


class PresentedStoryState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp: float = Field(ge=0)
    # These are deliberately display-ready values.  Scene ids and semantic ids
    # remain internal to the timeline and are never sent to the browser.
    scene_number: int | None = Field(default=None, ge=1)
    scene_summary: str | None = None
    current_goal: str | None = None
    timeline_position: str | None = None
    active_characters: list["PresentedCharacter"] = Field(default_factory=list)
    scene_mood: str | None = None
    important_objects: list[str] = Field(default_factory=list)
    story_summary: list[str] = Field(default_factory=list)
    memory_reminders: list[str] = Field(default_factory=list)
    unresolved_threads: list[str] = Field(default_factory=list)
    # Each tab is a pre-composed, interval-specific explanation. The browser
    # does not interpret graph data or reconstruct narrative context.
    tabs: "PresentedStoryTabs" = Field(default_factory=lambda: PresentedStoryTabs())


class PresentedCharacter(BaseModel):
    """A concise, child-friendly view of a character in the current interval."""

    model_config = ConfigDict(extra="forbid")
    name: str
    role: str
    emotion: str | None = None


class PresentedCauseEffect(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    cause: str
    effect: str


class PresentedStoryTabs(BaseModel):
    """Clean content for the fixed companion tabs at one timeline timestamp."""

    model_config = ConfigDict(extra="forbid")
    story_now: list[str] = Field(default_factory=list, max_length=4)
    relationships: list[str] = Field(default_factory=list)
    previous_event: str | None = None
    current_event: str | None = None
    next_event: str | None = None
    emotion: str | None = None
    cause_effect: list[PresentedCauseEffect] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    memories: list[str] = Field(default_factory=list, max_length=2)
