"""Builds immutable raw observations at the perception-to-semantics boundary."""
from hashlib import sha256

from schemas.detection import DetectionResponse
from schemas.grounding import GroundingResponse
from schemas.observation import FrameObservation, ObservationDetection
from schemas.understanding import UnderstandingResponse


class ObservationFactory:
    """Captures model output faithfully without assigning movie meaning."""

    def create(
        self,
        *,
        movie_id: str,
        scene_id: str,
        frame_hash: str,
        timestamp_seconds: float,
        detection: DetectionResponse,
        understanding: UnderstandingResponse,
        grounding: GroundingResponse | None,
    ) -> FrameObservation:
        observation_id = _id("observation", f"{movie_id}:{scene_id}:{timestamp_seconds:.3f}:{frame_hash}")
        return FrameObservation(
            id=observation_id,
            movie_id=movie_id,
            scene_id=scene_id,
            frame_hash=frame_hash,
            timestamp_seconds=timestamp_seconds,
            model_sources=[detection.model, understanding.model, *([grounding.model] if grounding else [])],
            # Deliberately retained only here. SemanticGraphBuilder never turns
            # this caption into a semantic claim or user-facing sentence.
            raw_florence_caption=understanding.scene_description,
            yolo_detections=[
                ObservationDetection(
                    id=_id("yolo", f"{observation_id}:{index}:{item.label}"), label=item.label,
                    model_source=detection.model, confidence=item.confidence, bounding_box=item.bbox,
                )
                for index, item in enumerate(detection.detections)
            ],
            grounding_detections=[
                ObservationDetection(
                    id=_id("grounding", f"{observation_id}:{index}:{item.matched_object}"), label=item.matched_object,
                    model_source=grounding.model, confidence=item.confidence, bounding_box=item.bbox,
                )
                for index, item in enumerate(grounding.matches if grounding else [])
            ],
            actions=understanding.detected_actions,
            interactions=understanding.interactions,
        )


def _id(kind: str, value: str) -> str:
    return f"{kind}-{sha256(value.encode('utf-8')).hexdigest()[:20]}"
