"""Model-agnostic contract for perception-only scene understanding."""
from abc import ABC, abstractmethod

from PIL import Image

from schemas.understanding import VisionUnderstanding


class VisionLanguageModel(ABC):
    """Describe visual evidence without assigning character identity or semantic relationships."""

    @abstractmethod
    def understand(self, image: Image.Image) -> tuple[VisionUnderstanding, str]:
        """Return perception fields and the configured model identifier."""
