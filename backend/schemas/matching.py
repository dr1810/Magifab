"""Structured output schemas for verified semantic matching only."""
from pydantic import BaseModel, ConfigDict, Field

from schemas.fusion import UnifiedEntity, UnifiedSceneRepresentation
from schemas.knowledge import SemanticMovieKnowledge


class MatchedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(min_length=1)


class CharacterMatch(MatchedFact):
    entity: UnifiedEntity


class SemanticMatchResult(BaseModel):
    """Verified facts only. Empty lists mean no match, never an inferred fallback."""
    model_config = ConfigDict(extra="forbid")
    character_found: bool
    characters: list[CharacterMatch] = Field(default_factory=list)
    locations: list[MatchedFact] = Field(default_factory=list)
    objects: list[MatchedFact] = Field(default_factory=list)
    relationships: list[MatchedFact] = Field(default_factory=list)
    events: list[MatchedFact] = Field(default_factory=list)
    timeline_positions: list[MatchedFact] = Field(default_factory=list)


class SemanticMatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene: UnifiedSceneRepresentation
    knowledge: SemanticMovieKnowledge
