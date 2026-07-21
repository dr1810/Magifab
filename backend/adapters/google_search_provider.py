"""Google Search grounding adapter used only for unresolved, approved entities."""
from __future__ import annotations

from config import Settings
from models.movie_pipeline import SearchProvider
from schemas.movie_pipeline import SearchResult


class GoogleSearchConfigurationError(RuntimeError):
    pass


class GoogleSearchGroundingProvider(SearchProvider):
    """Uses Google's Search grounding capability and persists cited web evidence only."""
    def __init__(self, settings: Settings) -> None:
        self._key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        self._model = settings.gemini_model
        self._client = None

    def search(self, query: str) -> list[SearchResult]:
        client = self._client_or_raise()
        from google.genai import types
        response = client.models.generate_content(
            model=self._model,
            contents=f"Search Google for this entity-identification query: {query}. Return a brief factual result with no speculation.",
            config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
        )
        metadata = getattr(response.candidates[0], "grounding_metadata", None) if getattr(response, "candidates", None) else None
        chunks = getattr(metadata, "grounding_chunks", []) if metadata else []
        snippet = " ".join(str(getattr(response, "text", "")).split())[:1_500]
        results: list[SearchResult] = []
        seen: set[str] = set()
        for chunk in chunks:
            web = getattr(chunk, "web", None)
            url = str(getattr(web, "uri", "")) if web else ""
            if not url or url in seen:
                continue
            seen.add(url)
            results.append(SearchResult(title=str(getattr(web, "title", "")), snippet=snippet, url=url, confidence=0.65))
            if len(results) == 3:
                break
        return results

    def _client_or_raise(self):
        if not self._key:
            raise GoogleSearchConfigurationError("GEMINI_API_KEY is required for configured Google Search grounding")
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self._key)
        return self._client
