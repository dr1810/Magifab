"""HTTP schemas for text-guided object localization without semantic interpretation."""
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GroundingRequest(BaseModel):
    """An image plus explicit visible-object phrases to locate in that image."""
    model_config = ConfigDict(extra="forbid")
    image: str = Field(min_length=8)
    queries: list[str] = Field(min_length=1, max_length=20)

    @field_validator("image")
    @classmethod
    def validate_image(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("image must not be empty")
        return value

    @field_validator("queries")
    @classmethod
    def validate_queries(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not cleaned:
            raise ValueError("queries must contain at least one non-empty object phrase")
        return cleaned


class GroundedObject(BaseModel):
    """A text-grounded visual object, never a movie-character identity."""
    model_config = ConfigDict(extra="forbid")
    matched_object: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    bbox: list[float] = Field(min_length=4, max_length=4)


class GroundingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matches: list[GroundedObject] = Field(default_factory=list)
    model: str
