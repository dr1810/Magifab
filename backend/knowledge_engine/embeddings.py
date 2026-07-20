"""Small deterministic embedding adapter suitable for local development and tests.

Production injects a semantic embedding provider (for example OpenAI or a
self-hosted model) behind the same contract; vectors remain independently
persisted and never depend on the request's current playback position.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> tuple[float, ...]: ...


class HashEmbeddingProvider:
    """Stable lexical projection for offline engine verification."""

    def __init__(self, dimensions: int = 256) -> None:
        self._dimensions = dimensions

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self._dimensions
        for token in re.findall(r"[a-z0-9']+", text.casefold()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self._dimensions
            vector[index] += 1.0
        magnitude = math.sqrt(sum(value * value for value in vector))
        return tuple(value / magnitude for value in vector) if magnitude else tuple(vector)


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))
