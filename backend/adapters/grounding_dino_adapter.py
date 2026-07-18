"""Lazy Hugging Face Grounding DINO adapter for text-guided object localization."""
import logging
from threading import Lock

import torch
from PIL import Image

from config import Settings
from models.text_guided_object_localizer import TextGuidedObjectLocalizer
from schemas.grounding import GroundedObject

logger = logging.getLogger(__name__)


class GroundingDINOAdapter(TextGuidedObjectLocalizer):
    """The only module coupled to Grounding DINO and Hugging Face inference details."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._model = None
        self._processor = None
        self._load_lock = Lock()
        self._inference_lock = Lock()

    def locate(self, image: Image.Image, queries: list[str]) -> tuple[list[GroundedObject], str]:
        with self._inference_lock:
            model, processor = self._load()
            inputs = processor(images=image, text=[queries], return_tensors="pt").to(self._device())
            with torch.inference_mode():
                outputs = model(**inputs)
            result = processor.post_process_grounded_object_detection(
                outputs,
                inputs.input_ids,
                threshold=self._settings.grounding_dino_box_threshold,
                text_threshold=self._settings.grounding_dino_text_threshold,
                target_sizes=[(image.height, image.width)],
            )[0]
        labels = result.get("text_labels", result.get("labels", []))
        matches = [
            GroundedObject(
                matched_object=str(label).strip(),
                confidence=float(score.item()),
                bbox=_xyxy_to_xywh(box.tolist()),
            )
            for box, score, label in zip(result["boxes"], result["scores"], labels, strict=True)
            if str(label).strip()
        ]
        return matches, self._settings.grounding_dino_model_id

    def _device(self) -> str:
        if self._settings.grounding_dino_device != "auto":
            return self._settings.grounding_dino_device
        return "mps" if torch.backends.mps.is_available() else "cpu"

    def _load(self):
        if self._model is not None and self._processor is not None:
            return self._model, self._processor
        with self._load_lock:
            if self._model is None or self._processor is None:
                try:
                    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
                except ImportError as error:
                    raise RuntimeError("transformers must be installed to use Grounding DINO") from error
                device = self._device()
                logger.info("Loading Grounding DINO", extra={"model": self._settings.grounding_dino_model_id, "device": device})
                self._processor = AutoProcessor.from_pretrained(self._settings.grounding_dino_model_id)
                self._model = AutoModelForZeroShotObjectDetection.from_pretrained(
                    self._settings.grounding_dino_model_id,
                    torch_dtype=torch.float32,
                ).eval().to(device)
        return self._model, self._processor

    def preload(self) -> None:
        self._load()


def _xyxy_to_xywh(box: list[float]) -> list[float]:
    x_min, y_min, x_max, y_max = (float(value) for value in box)
    return [x_min, y_min, x_max - x_min, y_max - y_min]
