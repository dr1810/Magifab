"""Florence-2 adapter; all Florence-specific prompts and parsing stay at this boundary."""
import logging
import re
from threading import Lock

import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor

from config import Settings
from models.vision_language_model import VisionLanguageModel
from schemas.understanding import VisionUnderstanding

logger = logging.getLogger(__name__)


class FlorenceAdapter(VisionLanguageModel):
    """Lazily loads Florence-2 Base and exposes perception-safe output fields."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._model = None
        self._processor = None
        self._load_lock = Lock()
        self._inference_lock = Lock()

    def _device(self) -> str:
        if self._settings.florence_device != "auto":
            return self._settings.florence_device
        return "mps" if torch.backends.mps.is_available() else "cpu"

    def _load(self) -> tuple[AutoModelForCausalLM, AutoProcessor]:
        if self._model is not None and self._processor is not None:
            return self._model, self._processor
        with self._load_lock:
            if self._model is None or self._processor is None:
                device = self._device()
                logger.info("Loading Florence vision-language model", extra={"model": self._settings.florence_model_id, "device": device})
                self._processor = AutoProcessor.from_pretrained(self._settings.florence_model_id, trust_remote_code=True)
                self._model = AutoModelForCausalLM.from_pretrained(
                    self._settings.florence_model_id,
                    trust_remote_code=True,
                    torch_dtype=torch.float32,
                ).eval().to(device)
        return self._model, self._processor

    def _run_task(self, task: str, image: Image.Image):
        model, processor = self._load()
        inputs = processor(text=task, images=image, return_tensors="pt")
        device = self._device()
        inputs = {key: value.to(device) for key, value in inputs.items()}
        generated_ids = model.generate(**inputs, max_new_tokens=self._settings.florence_max_new_tokens, do_sample=False)
        generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
        return processor.post_process_generation(generated_text, task=task, image_size=(image.width, image.height))

    def understand(self, image: Image.Image) -> tuple[VisionUnderstanding, str]:
        # Florence task prompts are visual perception operations, not semantic movie reasoning.
        with self._inference_lock:
            caption_result = self._run_task("<MORE_DETAILED_CAPTION>", image)
            objects_result = self._run_task("<OD>", image)
        caption = str(caption_result.get("<MORE_DETAILED_CAPTION>", "")).strip() or "A movie frame."
        object_data = objects_result.get("<OD>", {})
        labels = object_data.get("labels", []) if isinstance(object_data, dict) else []
        objects = _unique_strings(labels)
        return VisionUnderstanding(
            scene_description=caption,
            detected_actions=_extract_actions(caption),
            environment=_extract_environment(caption),
            important_objects=objects,
            interactions=_extract_interactions(caption),
        ), self._settings.florence_model_id


def _unique_strings(values: object) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip())) if isinstance(values, list) else []


def _extract_actions(caption: str) -> list[str]:
    """Expose only action words explicitly present in Florence's own caption."""
    return _matching_phrases(caption, ("walking", "running", "standing", "sitting", "holding", "looking", "talking", "speaking", "playing", "eating", "driving"))


def _extract_environment(caption: str) -> str:
    """Return an environment term only when Florence explicitly captioned it."""
    matches = _matching_phrases(caption, ("forest", "woods", "street", "road", "room", "kitchen", "house", "park", "beach", "field", "mountain", "sky", "water"))
    return matches[0] if matches else ""


def _extract_interactions(caption: str) -> list[str]:
    """Return caption clauses that explicitly describe an interaction; do not infer one."""
    clauses = re.split(r"[,.;]", caption)
    return [clause.strip() for clause in clauses if re.search(r"\b(with|beside|next to|talking to|looking at)\b", clause, flags=re.IGNORECASE)]


def _matching_phrases(text: str, vocabulary: tuple[str, ...]) -> list[str]:
    lower = text.lower()
    return [term for term in vocabulary if re.search(rf"\b{re.escape(term)}\b", lower)]
