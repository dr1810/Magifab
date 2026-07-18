"""Lazy InsightFace adapter for RetinaFace detection and ArcFace face embeddings."""
import logging
from threading import Lock

import numpy as np
from PIL import Image

from config import Settings
from models.face_embedding_extractor import FaceEmbeddingExtractor

logger = logging.getLogger(__name__)


class RetinaFaceArcFaceAdapter(FaceEmbeddingExtractor):
    """Model-specific face perception adapter; it never reads Semantic Movie Knowledge."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._analyzer = None
        self._load_lock = Lock()

    def extract(self, image: Image.Image) -> tuple[list[tuple[list[float], float, list[float]]], str, str]:
        analyzer = self._get_analyzer()
        bgr_image = np.ascontiguousarray(np.asarray(image.convert("RGB"))[:, :, ::-1])
        faces = analyzer.get(bgr_image)
        observations: list[tuple[list[float], float, list[float]]] = []
        for face in faces:
            x_min, y_min, x_max, y_max = (float(value) for value in face.bbox)
            embedding = [float(value) for value in face.normed_embedding]
            observations.append(([x_min, y_min, x_max - x_min, y_max - y_min], float(face.det_score), embedding))
        return observations, f"RetinaFace ({self._settings.face_model_pack})", f"ArcFace ({self._settings.face_model_pack})"

    def _get_analyzer(self):
        if self._analyzer is not None:
            return self._analyzer
        with self._load_lock:
            if self._analyzer is None:
                try:
                    from insightface.app import FaceAnalysis
                except ImportError as error:
                    raise RuntimeError("insightface must be installed to use face verification") from error
                providers = [provider.strip() for provider in self._settings.face_onnx_providers.split(",") if provider.strip()]
                logger.info("Loading RetinaFace and ArcFace models", extra={"model_pack": self._settings.face_model_pack, "providers": providers})
                analyzer = FaceAnalysis(
                    name=self._settings.face_model_pack,
                    allowed_modules=["detection", "recognition"],
                    providers=providers,
                )
                analyzer.prepare(ctx_id=0, det_size=(self._settings.face_detection_size, self._settings.face_detection_size))
                self._analyzer = analyzer
        return self._analyzer
