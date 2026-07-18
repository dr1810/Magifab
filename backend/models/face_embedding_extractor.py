"""Replaceable face-detection and embedding contract."""
from abc import ABC, abstractmethod

from PIL import Image


class FaceEmbeddingExtractor(ABC):
    """Produces face boxes and embeddings only; it cannot identify movie characters."""

    @abstractmethod
    def extract(self, image: Image.Image) -> tuple[list[tuple[list[float], float, list[float]]], str, str]:
        """Return pixel-space boxes, detector confidence, embeddings, and detector/embedding model names."""
