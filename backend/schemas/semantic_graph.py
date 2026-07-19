"""Graph-native semantic claims derived from observations, with full provenance."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SemanticClaimKind = Literal[
    "character_present", "object_present", "event", "relationship", "timeline_change",
    "emotion", "callback", "scene_state",
]

ClaimEvidenceOrigin = Literal[
    "perception_verified",
    "movie_knowledge_supported",
    "reasoning_inferred",
]


class SemanticClaim(BaseModel):
    """A movie-world assertion. It never stores a raw model caption."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    kind: SemanticClaimKind
    scene_id: str = Field(min_length=1)
    timestamp_seconds: float = Field(ge=0)
    # Kept alongside the point timestamp for backwards compatibility.  The
    # timestamp engine normalizes every claim into a movie-time interval.
    timestamp_start: float | None = Field(default=None, ge=0)
    timestamp_end: float | None = Field(default=None, ge=0)
    subject_id: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object_id: str | None = None
    value: str = ""
    confidence: float = Field(ge=0, le=1)
    observation_ids: list[str] = Field(min_length=1)
    # A claim may be visually verified and also cite a catalog entity.  The
    # origin tells downstream consumers which boundary established the fact;
    # the catalog reference never substitutes for frame evidence.
    evidence_origin: ClaimEvidenceOrigin = "perception_verified"
    knowledge_ids: list[str] = Field(default_factory=list)
    supporting_claim_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _timestamp_interval(self):
        if self.timestamp_start is None:
            self.timestamp_start = self.timestamp_seconds
        if self.timestamp_end is None:
            self.timestamp_end = self.timestamp_seconds
        if self.timestamp_end < self.timestamp_start:
            raise ValueError("timestamp_end must not precede timestamp_start")
        return self
