"""Validated HTTP schemas for the Phase 2 object-detection API."""
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DetectionRequest(BaseModel):
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


class Detection(BaseModel):
    """An object class and a pixel-space [x, y, width, height] bounding box."""
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    bbox: list[float] = Field(min_length=4, max_length=4)


class DetectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detections: list[Detection]
    model: str
