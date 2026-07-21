"""Evidence-bounded OpenAI synthesis of the canonical MagiFab scene document."""
from __future__ import annotations

import json

from openai import OpenAI

from adapters.openai_personalizer import PersonalizationConfigurationError, PersonalizationProviderError
from config import Settings
from models.movie_pipeline import SceneReasoningProvider
from schemas.movie_pipeline import CanonicalMagiFabScene, GeminiVisualScene, SearchContext


class OpenAISceneReasoner(SceneReasoningProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: OpenAI | None = None

    def reason(self, visual_scene: GeminiVisualScene, search_context: list[SearchContext]) -> CanonicalMagiFabScene:
        payload = {"gemini_visual_json": visual_scene.model_dump(mode="json"), "google_search_evidence": [item.model_dump(mode="json") for item in search_context]}
        try:
            response = self._client_or_raise().responses.create(
                model=self._settings.openai_model,
                instructions=_instructions(),
                input=[{"role": "user", "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)}]}],
                max_output_tokens=max(self._settings.openai_max_output_tokens, 1_200),
                text={"format": {"type": "json_schema", "name": "canonical_magifab_scene", "strict": True, "schema": CanonicalMagiFabScene.model_json_schema()}},
            )
            return CanonicalMagiFabScene.model_validate_json(response.output_text)
        except PersonalizationConfigurationError:
            raise
        except Exception as error:
            raise PersonalizationProviderError("OpenAI could not produce a canonical MagiFab scene") from error

    def _client_or_raise(self) -> OpenAI:
        if self._client:
            return self._client
        key = self._settings.openai_api_key.get_secret_value() if self._settings.openai_api_key else None
        if not key:
            raise PersonalizationConfigurationError("OPENAI_API_KEY is not configured on the backend")
        self._client = OpenAI(api_key=key)
        return self._client


def _instructions() -> str:
    return """You are MagiFab's evidence-bounded reasoning engine for an accessibility companion. Produce exactly the canonical scene JSON schema.

Use the Gemini visual JSON as the primary evidence. Google Search results are secondary evidence only: resolve an Unknown identity only when a result directly supports the visual description and query. Do not treat a search-result title, snippet, or URL as proof by itself. Keep Unknown and low confidence when evidence is insufficient. Do not invent names, dialogue, plot knowledge, causes, relationships, emotions, locations, or future events. Merge only clearly duplicate entities.

Infer simple relationships, immediate cause/effect, memory cues, timeline refinement, difficulty points, one useful visual aid, and a concise accessibility explanation only when grounded in the supplied evidence. Search context in your output must reproduce the supplied evidence without additions."""
