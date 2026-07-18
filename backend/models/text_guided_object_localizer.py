"""Replaceable contract for text-guided object localization."""
from abc import ABC, abstractmethod

from PIL import Image

from schemas.grounding import GroundedObject


class TextGuidedObjectLocalizer(ABC):
    """Finds requested visual objects and boxes only; it cannot identify movie characters."""

    @abstractmethod
    def locate(self, image: Image.Image, queries: list[str]) -> tuple[list[GroundedObject], str]:
        """Return grounded boxes for explicit object phrases and the model identifier."""
