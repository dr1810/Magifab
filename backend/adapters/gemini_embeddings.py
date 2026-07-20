"""Gemini semantic embedding adapter using the official REST API."""
from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from config import Settings
from services.semantic_retrieval import SemanticEmbeddingProvider


class GeminiEmbeddingError(RuntimeError):
    pass


class GeminiEmbeddingProvider(SemanticEmbeddingProvider):
    def __init__(self, settings: Settings) -> None:
        self._key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        self._model = settings.gemini_embedding_model

    def embed_documents(self, texts: list[str]) -> list[tuple[float, ...]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self._embed(text)

    def _embed(self, text: str) -> tuple[float, ...]:
        if not self._key:
            raise GeminiEmbeddingError("GEMINI_API_KEY is not configured")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:embedContent"
        payload = {"model": f"models/{self._model}", "content": {"parts": [{"text": text}]}, "output_dimensionality": 768}
        request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "x-goog-api-key": self._key}, method="POST")
        try:
            with urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
            values = body.get("embedding", {}).get("values")
            if not isinstance(values, list) or not values:
                raise GeminiEmbeddingError("Gemini returned no embedding")
            return tuple(float(value) for value in values)
        except (URLError, OSError, ValueError, TypeError) as error:
            raise GeminiEmbeddingError("Unable to create Gemini embedding") from error
