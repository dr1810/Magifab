"""Structured, caller-supplied semantic movie knowledge for conservative matching."""
from pydantic import BaseModel, ConfigDict, Field


class SemanticCharacter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    perception_labels: list[str] = Field(default_factory=list)


class SemanticLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)


class SemanticObject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    perception_labels: list[str] = Field(default_factory=list)


class SemanticRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    from_character_id: str = Field(min_length=1)
    to_character_id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class TimelinePosition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    description: str = Field(min_length=1)


class SemanticEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence_terms: list[str] = Field(min_length=1)
    timeline_position_id: str | None = None


class SemanticMovieKnowledge(BaseModel):
    """Knowledge base slice for one movie; no model inference or automatic enrichment occurs here."""
    model_config = ConfigDict(extra="forbid")
    movie_id: str = Field(min_length=1)
    characters: list[SemanticCharacter] = Field(default_factory=list)
    locations: list[SemanticLocation] = Field(default_factory=list)
    objects: list[SemanticObject] = Field(default_factory=list)
    relationships: list[SemanticRelationship] = Field(default_factory=list)
    events: list[SemanticEvent] = Field(default_factory=list)
    timeline_positions: list[TimelinePosition] = Field(default_factory=list)
