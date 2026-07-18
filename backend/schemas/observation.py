"""Raw, provenance-bearing model evidence. These records are never UI contracts."""
from pydantic import BaseModel, ConfigDict, Field


class ObservationDetection(BaseModel):
    """One raw detection or grounding match from a single model."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    model_source: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    bounding_box: list[float] | None = Field(default=None, min_length=4, max_length=4)


class FrameObservation(BaseModel):
    """Immutable raw evidence for one movie frame; captions are evidence, never facts."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    movie_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    frame_hash: str = Field(min_length=16, max_length=128)
    timestamp_seconds: float = Field(ge=0)
    model_sources: list[str] = Field(min_length=1)
    raw_florence_caption: str = ""
    yolo_detections: list[ObservationDetection] = Field(default_factory=list)
    grounding_detections: list[ObservationDetection] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    interactions: list[str] = Field(default_factory=list)

