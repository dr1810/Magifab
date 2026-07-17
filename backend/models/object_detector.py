"""Model-agnostic contract for visual object detection."""
from abc import ABC, abstractmethod

from PIL import Image

from schemas.detection import Detection


class ObjectDetector(ABC):
    """Detect visible object classes and boxes, never movie-character identities."""

    @abstractmethod
    def detect(self, image: Image.Image) -> tuple[list[Detection], str]:
        """Return detections and the configured model identifier."""
