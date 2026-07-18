"""Adapters that normalize existing YOLO and Florence response schemas for fusion."""
from models.perception_evidence_adapter import PerceptionEvidenceAdapter
from schemas.detection import DetectionResponse
from schemas.fusion import PerceptionContribution, UnifiedEntity
from schemas.understanding import UnderstandingResponse

_ANIMAL_LABELS = frozenset({
    "bird", "cat", "cow", "dog", "elephant", "giraffe", "horse", "sheep", "bear", "zebra",
    "squirrel", "rabbit", "fox", "deer", "monkey", "lion", "tiger",
})


def classify_entity(label: str) -> str:
    """Structural category mapping only; it does not name or match any character."""
    normalized = label.strip().lower()
    if normalized == "person":
        return "person"
    if normalized in _ANIMAL_LABELS:
        return "animal"
    return "object" if normalized else "unknown"


class ObjectDetectionEvidenceAdapter(PerceptionEvidenceAdapter[DetectionResponse]):
    """Converts bounding-box detector output into normalized visual entities."""

    def to_contribution(self, evidence: DetectionResponse) -> PerceptionContribution:
        return PerceptionContribution(
            provider="object_detection",
            entities=[
                UnifiedEntity(
                    label=detection.label,
                    category=classify_entity(detection.label),
                    bounding_box=detection.bbox,
                    confidence=detection.confidence,
                    sources=["object_detection"],
                    visual_attributes={"model": [evidence.model]},
                )
                for detection in evidence.detections
            ],
            visual_attributes={"models": [evidence.model]},
        )


class VisionUnderstandingEvidenceAdapter(PerceptionEvidenceAdapter[UnderstandingResponse]):
    """Converts Florence's caption-backed fields into text-only perception evidence."""

    def to_contribution(self, evidence: UnderstandingResponse) -> PerceptionContribution:
        return PerceptionContribution(
            provider="scene_understanding",
            scene_description=evidence.scene_description,
            entities=[
                UnifiedEntity(
                    label=label,
                    category=classify_entity(label),
                    sources=["scene_understanding"],
                    visual_attributes={"model": [evidence.model]},
                )
                for label in evidence.important_objects
            ],
            environment=evidence.environment,
            actions=evidence.detected_actions,
            interactions=evidence.interactions,
            visual_attributes={"models": [evidence.model]},
        )
