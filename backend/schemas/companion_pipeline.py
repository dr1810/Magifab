"""End-to-end retrieval-first runtime request and response contracts."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.accessibility_reasoning import AccessibilityDrawerContent, AccessibilityProfile, AccessibilityReasoningResult, CompanionProfile
from schemas.accessibility_presentation import AccessibilityPresentation
from schemas.personalization import GPTPersonalizationResponse


class CompanionPipelineRequest(BaseModel):
    """Interaction requests retrieve prepared scene knowledge; they never carry an image."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str = Field(min_length=1)
    timestamp_seconds: float = Field(ge=0)
    scene_id: str | None = None
    scene_summary: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=2_000)
    intent: str = Field(default="general", min_length=1, max_length=100)
    image: str | None = Field(default=None, min_length=8)
    grounding_queries: list[str] = Field(default_factory=list, max_length=20)
    verify_faces: bool = False
    accessibility_profile: AccessibilityProfile
    companion_profile: CompanionProfile

    @field_validator("image")
    @classmethod
    def normalize_image(cls, value: str | None) -> str | None:
        return value.strip() if value else None


class CompanionPipelineResponse(BaseModel):
    """A personalized response plus the verified structured facts that produced it."""
    model_config = ConfigDict(extra="forbid")
    knowledge_source: Literal["retrieved", "expanded"]
    response_cache_hit: bool
    cache_key: str
    knowledge_revision: int = Field(ge=1)
    response: GPTPersonalizationResponse
    accessibility_content: AccessibilityReasoningResult


class ScenePreparationRequest(BaseModel):
    """One representative frame for a scene, supplied before prompts are exposed."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    timestamp_seconds: float = Field(ge=0)
    scene_summary: str = Field(min_length=1)
    image: str = Field(min_length=8)
    # Optional caller hints supplement (never replace) the labels discovered by
    # YOLO. Keeping this on the preparation contract makes grounding extensible
    # for uploaded movies without coupling the UI to a particular model.
    grounding_queries: list[str] = Field(default_factory=list, max_length=20)
    verify_faces: bool = False
    accessibility_profile: AccessibilityProfile
    companion_profile: CompanionProfile


class PreparedCharacter(BaseModel):
    """A named identity only when the semantic matcher verified it."""
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    confidence: float = Field(ge=0, le=1)
    bounding_box: list[float] | None = Field(default=None, min_length=4, max_length=4)
    verified: bool = True


class PreparedObject(BaseModel):
    """A visible object backed by cached perception evidence."""
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    confidence: float = Field(ge=0, le=1)
    bounding_box: list[float] | None = Field(default=None, min_length=4, max_length=4)
    sources: list[str] = Field(default_factory=list)


class SemanticGraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    kind: str
    confidence: float | None = Field(default=None, ge=0, le=1)


class SemanticGraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_id: str
    to_id: str
    kind: str
    label: str = ""


class PreparedSemanticGraph(BaseModel):
    """Read-only graph projection of the persisted Semantic Movie Knowledge."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str
    scene_id: str
    revision: int = Field(ge=1)
    nodes: list[SemanticGraphNode] = Field(default_factory=list)
    edges: list[SemanticGraphEdge] = Field(default_factory=list)


class PreparedPromptBubble(BaseModel):
    """A ready-to-render prompt; selecting it performs retrieval-only reasoning."""
    model_config = ConfigDict(extra="forbid")
    id: str
    type: str
    title: str
    question: str
    text: str
    target_entity: str | None = None
    bounding_box: list[float] | None = Field(default=None, min_length=4, max_length=4)
    priority: int = Field(ge=1)
    claim_ids: list[str] = Field(default_factory=list)
    cached: bool = True


class PreparationCacheMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cache_key: str
    frame_hash: str | None = None
    knowledge_revision: int = Field(ge=1)
    knowledge_source: Literal["retrieved", "expanded"]
    semantic_map_cached: bool
    reasoning_cached: bool = True


class ScenePreparationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    knowledge_source: Literal["retrieved", "expanded"]
    knowledge_revision: int = Field(ge=1)
    presentation: AccessibilityPresentation
    accessibility_content: AccessibilityReasoningResult
    # First-class preparation data lets clients render the prompt panel and
    # visual drawer immediately, rather than reconstructing them from a prose
    # scene summary.
    scene_summary: str
    prompt_bubbles: list[PreparedPromptBubble] = Field(default_factory=list)
    visual_drawer: AccessibilityDrawerContent
    cache: PreparationCacheMetadata
