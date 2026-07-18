"""Ultralytics YOLO adapter. This is the only Phase 2 module coupled to YOLO."""
import logging
from threading import Lock

import torch
from PIL import Image
from ultralytics import YOLO

from config import Settings
from models.object_detector import ObjectDetector
from schemas.detection import Detection

logger = logging.getLogger(__name__)


class YOLOAdapter(ObjectDetector):
    """Lazily loads YOLOv11n and emits ordinary object labels and pixel boxes."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._model: YOLO | None = None
        self._load_lock = Lock()

    def _device(self) -> str:
        if self._settings.yolo_device != "auto":
            return self._settings.yolo_device
        return "mps" if torch.backends.mps.is_available() else "cpu"

    def _get_model(self) -> YOLO:
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is None:
                logger.info("Loading YOLO detector", extra={"model": self._settings.yolo_model_id, "device": self._device()})
                self._model = YOLO(self._settings.yolo_model_id)
        return self._model

    def preload(self) -> None:
        self._get_model()

    def detect(self, image: Image.Image) -> tuple[list[Detection], str]:
        results = self._get_model().predict(
            source=image,
            conf=self._settings.detection_confidence_threshold,
            device=self._device(),
            verbose=False,
        )
        detections: list[Detection] = []
        for result in results:
            names = result.names
            for box in result.boxes:
                x_min, y_min, x_max, y_max = (float(value) for value in box.xyxy[0].tolist())
                class_id = int(box.cls[0].item())
                label = names[class_id] if isinstance(names, dict) else names[class_id]
                detections.append(Detection(
                    label=str(label),
                    confidence=float(box.conf[0].item()),
                    bbox=[x_min, y_min, x_max - x_min, y_max - y_min],
                ))
        return detections, self._settings.yolo_model_id
