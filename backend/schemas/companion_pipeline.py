"""End-to-end retrieval-first runtime request and response contracts."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.accessibility_reasoning import AccessibilityProfile, CompanionProfile
from schemas.interval_state import IntervalState


class CompanionInterval(BaseModel):
    """Content-neutral unit produced by every MagiFab content provider."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    contentId: str = Field(min_length=1)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    timestamp: float = Field(ge=0)
    image: str = Field(min_length=8)
    text: str = Field(default="", max_length=100_000)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("end")
    @classmethod
    def end_follows_start(cls, value: float, info) -> float:
        if value <= info.data.get("start", 0):
            raise ValueError("end must be greater than start")
        return value


class CompanionIntervalPreparationRequest(BaseModel):
    """The provider-agnostic boundary for companion preparation."""
    model_config = ConfigDict(extra="forbid")
    interval: CompanionInterval
    accessibility_profile: AccessibilityProfile
    companion_profile: CompanionProfile


class CompanionIntervalPromptRequest(BaseModel):
    """Provider-agnostic prompt lookup against a prepared content interval."""
    model_config = ConfigDict(extra="forbid")
    contentId: str = Field(min_length=1)
    timestamp: float = Field(ge=0)
    question: str = Field(min_length=1, max_length=2_000)
    intent: str = Field(default="general", min_length=1, max_length=100)
    grounding_queries: list[str] = Field(default_factory=list, max_length=20)
    verify_faces: bool = False
    accessibility_profile: AccessibilityProfile
    companion_profile: CompanionProfile


class CompanionPipelineRequest(BaseModel):
    """Interaction requests retrieve a prepared interval; they never carry an image."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str = Field(min_length=1)
    timestamp_seconds: float = Field(ge=0)
    question: str = Field(min_length=1, max_length=2_000)
    intent: str = Field(default="general", min_length=1, max_length=100)
    image: str | None = Field(default=None, min_length=8)
    grounding_queries: list[str] = Field(default_factory=list, max_length=20)
    verify_faces: bool = False
    conversation_id: str = Field(default="default", min_length=1, max_length=200)
    accessibility_profile: AccessibilityProfile
    companion_profile: CompanionProfile

    @field_validator("image")
    @classmethod
    def normalize_image(cls, value: str | None) -> str | None:
        return value.strip() if value else None


class CompanionPipelineResponse(IntervalState):
    """Prompt interaction returns the complete updated interval snapshot."""


class IntervalPreparationRequest(BaseModel):
    """One representative frame for a fixed interval, supplied during preprocessing."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str = Field(min_length=1)
    interval_id: str = Field(min_length=1)
    interval_number: int = Field(ge=0)
    interval_start: float = Field(ge=0)
    interval_end: float = Field(gt=0)
    # Optional catalog annotation. It may enrich matching but can never own
    # memory or playback identity.
    catalog_scene_id: str | None = None
    timestamp_seconds: float = Field(ge=0)
    image: str = Field(min_length=8)
    source_text: str = Field(default="", max_length=100_000)
    # Optional caller hints supplement (never replace) the labels discovered by
    # YOLO. Keeping this on the preparation contract makes grounding extensible
    # for uploaded movies without coupling the UI to a particular model.
    grounding_queries: list[str] = Field(default_factory=list, max_length=20)
    verify_faces: bool = False
    accessibility_profile: AccessibilityProfile
    companion_profile: CompanionProfile


class IntervalPreparationResponse(IntervalState):
    """Preparation returns the complete interval snapshot, with no envelope."""


class PreprocessingCompletionRequest(BaseModel):
    """Signals that all fixed intervals for a movie have been generated."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str = Field(min_length=1)
    expected_intervals: int = Field(ge=1)
