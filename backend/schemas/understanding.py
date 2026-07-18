"""Validated HTTP schemas for the Phase 3 vision-understanding API."""
from pydantic import BaseModel, ConfigDict, Field, field_validator


class UnderstandingRequest(BaseModel):
    """A base64 image or a base64 data URL."""
    model_config = ConfigDict(extra="forbid")
    image: str = Field(min_length=8)

    @field_validator("image")
    @classmethod
    def validate_image(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("image must not be empty")
        return value


class VisionUnderstanding(BaseModel):
    """Perception output only; all fields intentionally exclude character identity."""
    model_config = ConfigDict(extra="forbid")
    scene_description: str
    detected_actions: list[str] = Field(default_factory=list)
    environment: str = ""
    important_objects: list[str] = Field(default_factory=list)
    interactions: list[str] = Field(default_factory=list)


class UnderstandingResponse(VisionUnderstanding):
    model: str
