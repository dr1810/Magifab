"""Business service that depends only on the ObjectDetector contract."""
from PIL import Image

from models.object_detector import ObjectDetector
from schemas.detection import DetectionResponse


class ObjectDetectionService:
    """Coordinates detection without semantic or character-level reasoning."""

    def __init__(self, detector: ObjectDetector):
        self._detector = detector

    def detect(self, image: Image.Image) -> DetectionResponse:
        detections, model = self._detector.detect(image)
        return DetectionResponse(detections=detections, model=model)
