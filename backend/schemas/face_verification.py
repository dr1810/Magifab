"""HTTP-safe face-verification schemas; face embeddings never leave this API boundary."""
from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.knowledge import SemanticMovieKnowledge


class FaceVerificationRequest(BaseModel):
    """An image and the movie knowledge that holds enrolled, verified face references."""
    model_config = ConfigDict(extra="forbid")
    image: str = Field(min_length=8)
    knowledge: SemanticMovieKnowledge

    @field_validator("image")
    @classmethod
    def validate_image(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("image must not be empty")
        return value


class DetectedFace(BaseModel):
    """A detected face with no character identity attached."""
    model_config = ConfigDict(extra="forbid")
    bbox: list[float] = Field(min_length=4, max_length=4)
    detection_confidence: float = Field(ge=0, le=1)


class FaceVerification(BaseModel):
    """Verification result, emitted only when one enrolled character is confidently supported."""
    model_config = ConfigDict(extra="forbid")
    face: DetectedFace
    verified: bool
    verified_character_id: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class FaceVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    faces: list[FaceVerification] = Field(default_factory=list)
    detector_model: str
    embedding_model: str
