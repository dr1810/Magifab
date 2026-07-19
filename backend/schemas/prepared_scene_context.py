"""Persisted semantic context produced by interval preparation."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.reasoning_context import ReasoningContext


class PreparedSceneContext(BaseModel):
    """The exact graph-only context that /prepare supplied to reasoning."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str = Field(min_length=1)
    interval_id: str = Field(min_length=1)
    timestamp_seconds: float = Field(ge=0)
    preparation_cache_key: str = Field(min_length=1)
    semantic_cache_version: int = Field(ge=1)
    knowledge_revision: int = Field(ge=1)
    knowledge_source: Literal["retrieved", "expanded"]
    semantic_map_cached: bool
    reasoning_cached: bool = False
    frame_hash: str | None = Field(default=None, min_length=16, max_length=128)
    reasoning_context: ReasoningContext
