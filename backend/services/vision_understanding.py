"""Business service that depends only on the VisionLanguageModel contract."""
from PIL import Image

from models.vision_language_model import VisionLanguageModel
from schemas.understanding import UnderstandingResponse


class VisionUnderstandingService:
    """Coordinates scene perception without character or semantic reasoning."""

    def __init__(self, model: VisionLanguageModel):
        self._model = model

    def understand(self, image: Image.Image) -> UnderstandingResponse:
        understanding, model = self._model.understand(image)
        return UnderstandingResponse(**understanding.model_dump(), model=model)
