"""Process-wide owner for every heavyweight perception model."""
import logging
import platform
import time

import psutil

import torch

from adapters.florence_adapter import FlorenceAdapter
from adapters.grounding_dino_adapter import GroundingDINOAdapter
from adapters.yolo_adapter import YOLOAdapter
from config import Settings

logger = logging.getLogger(__name__)


class ModelManager:
    """Creates adapters once and explicitly controls their model lifetime."""

    def __init__(self, settings: Settings):
        self.settings = settings
        # Adapters are lightweight here. Their weights are not loaded until preload().
        self.yolo = YOLOAdapter(settings)
        self.florence = FlorenceAdapter(settings)
        self.grounding_dino = GroundingDINOAdapter(settings)

    def device(self) -> str:
        return "mps" if torch.backends.mps.is_available() else "cpu"

    def preload(self) -> None:
        """Load every shared model once, with actionable diagnostics on failure."""
        logger.info(
            "Starting backend: python=%s torch=%s device=%s mps_available=%s rss=%s mps=%s",
            platform.python_version(), torch.__version__, self.device(), torch.backends.mps.is_available(), self._memory(), self._mps_memory(),
        )
        self._load("YOLO", self.yolo.preload, "check the Ultralytics/YOLO checkpoint version and reinstall the pinned requirements")
        self._load("Florence-2", self.florence.preload, "clear the Hugging Face Florence cache and reinstall the pinned Transformers 4.x stack")
        self._load("Grounding DINO", self.grounding_dino.preload, "clear the Hugging Face Grounding DINO cache and confirm the pinned Transformers stack")
        logger.info("Initializing semantic services...")
        logger.info("Backend ready.")

    @classmethod
    def _load(cls, name: str, loader, recommendation: str) -> None:
        started = time.perf_counter()
        logger.info("Loading %s... rss=%s mps=%s", name, cls._memory(), cls._mps_memory())
        try:
            loader()
        except Exception as error:
            logger.exception("%s failed to load: %s. Recommended fix: %s", name, error, recommendation)
            raise RuntimeError(f"{name} failed startup self-test: {error}") from error
        logger.info("Finished %s in %.2fs rss=%s mps=%s", name, time.perf_counter() - started, cls._memory(), cls._mps_memory())

    @staticmethod
    def _memory() -> str:
        info = psutil.Process().memory_info()
        return f"rss={info.rss / 1024 / 1024:.1f}MiB shared={getattr(info, 'shared', 0) / 1024 / 1024:.1f}MiB"

    @staticmethod
    def _mps_memory() -> str:
        if not torch.backends.mps.is_available():
            return "unavailable"
        try:
            return f"allocated={torch.mps.current_allocated_memory() / 1024 / 1024:.1f}MiB"
        except RuntimeError as error:
            return f"unavailable ({error})"
