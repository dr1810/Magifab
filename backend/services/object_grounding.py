"""Application service for demand-driven object localization."""
from PIL import Image

from models.text_guided_object_localizer import TextGuidedObjectLocalizer
from schemas.grounding import GroundingResponse


class ObjectGroundingService:
    """Coordinates text-guided localization; it never performs semantic matching or GPT reasoning."""

    def __init__(self, localizer: TextGuidedObjectLocalizer):
        self._localizer = localizer

    def locate(self, image: Image.Image, queries: list[str]) -> GroundingResponse:
        matches, model = self._localizer.locate(image, queries)
        return GroundingResponse(matches=matches, model=model)
