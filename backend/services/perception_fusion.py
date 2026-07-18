"""Fusion service for perception evidence only; no semantic or character-level reasoning."""
from collections.abc import Iterable

from adapters.perception_evidence import FaceVerificationEvidenceAdapter, GroundingEvidenceAdapter, ObjectDetectionEvidenceAdapter, VisionUnderstandingEvidenceAdapter
from schemas.detection import DetectionResponse
from schemas.face_verification import FaceVerificationResponse
from schemas.fusion import PerceptionContribution, UnifiedEntity, UnifiedSceneRepresentation
from schemas.grounding import GroundingResponse
from schemas.understanding import UnderstandingResponse


class PerceptionFusionService:
    """Merges normalized perception contributions into one current-frame representation."""

    def __init__(
        self,
        detection_adapter: ObjectDetectionEvidenceAdapter | None = None,
        vision_adapter: VisionUnderstandingEvidenceAdapter | None = None,
        grounding_adapter: GroundingEvidenceAdapter | None = None,
        face_adapter: FaceVerificationEvidenceAdapter | None = None,
    ):
        self._detection_adapter = detection_adapter or ObjectDetectionEvidenceAdapter()
        self._vision_adapter = vision_adapter or VisionUnderstandingEvidenceAdapter()
        self._grounding_adapter = grounding_adapter or GroundingEvidenceAdapter()
        self._face_adapter = face_adapter or FaceVerificationEvidenceAdapter()

    def fuse_current_outputs(
        self,
        object_detection: DetectionResponse,
        scene_understanding: UnderstandingResponse,
        grounding: GroundingResponse | None = None,
        face_verification: FaceVerificationResponse | None = None,
    ) -> UnifiedSceneRepresentation:
        """Fuse detector, scene-understanding, and optional grounding evidence at a stable boundary."""
        contributions = [
            self._detection_adapter.to_contribution(object_detection),
            self._vision_adapter.to_contribution(scene_understanding),
        ]
        if grounding is not None:
            contributions.append(self._grounding_adapter.to_contribution(grounding))
        if face_verification is not None:
            contributions.append(self._face_adapter.to_contribution(face_verification))
        return self.fuse(contributions)

    def fuse(self, contributions: Iterable[PerceptionContribution]) -> UnifiedSceneRepresentation:
        """Fuse any future normalized contribution without changing downstream schemas."""
        items = list(contributions)
        entities = self._deduplicate_text_only_entities(items)
        return UnifiedSceneRepresentation(
            scene_description=next((item.scene_description for item in items if item.scene_description), ""),
            entities=entities,
            people=[entity for entity in entities if entity.category == "person"],
            animals=[entity for entity in entities if entity.category == "animal"],
            objects=[entity for entity in entities if entity.category == "object"],
            environment=next((item.environment for item in items if item.environment), ""),
            actions=_unique(value for item in items for value in item.actions),
            interactions=_unique(value for item in items for value in item.interactions),
            visual_attributes=_merge_attributes(item.visual_attributes for item in items),
            providers=_unique(item.provider for item in items),
        )

    @staticmethod
    def _deduplicate_text_only_entities(items: list[PerceptionContribution]) -> list[UnifiedEntity]:
        """Prefer a detector box over duplicate caption-only labels; retain multiple real boxes."""
        entities: list[UnifiedEntity] = []
        labels_with_boxes = {entity.label.lower() for item in items for entity in item.entities if entity.bounding_box is not None}
        for item in items:
            for entity in item.entities:
                if entity.bounding_box is None and entity.label.lower() in labels_with_boxes:
                    continue
                entities.append(entity)
        return entities


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _merge_attributes(attributes: Iterable[dict[str, list[str]]]) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for attribute_set in attributes:
        for key, values in attribute_set.items():
            merged[key] = _unique([*merged.get(key, []), *values])
    return merged
