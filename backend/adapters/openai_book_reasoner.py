"""OpenAI reasoning boundary for extracted book chapters; it never handles video."""
from __future__ import annotations

import json

from openai import OpenAI

from adapters.openai_personalizer import PersonalizationConfigurationError, PersonalizationProviderError
from config import Settings
from schemas.book_pipeline import BookChapterResponse


class OpenAIBookReasoner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: OpenAI | None = None

    def reason(self, chapter: int, title: str, text: str, profile: dict[str, object]) -> BookChapterResponse:
        payload = {"chapter": chapter, "title": title, "extracted_text": text[:20_000], "user_companion_profile": profile}
        try:
            response = self._client_or_raise().responses.create(
                model=self._settings.openai_model,
                instructions=("You create MagiFab's accessible book artifacts from extracted text only. "
                              "Do not invent plot facts or use outside book knowledge. Produce a concise, personalized "
                              "chapter summary, character cards, relationships, locations, political/social context, "
                              "memory aids, timeline, glossary, and a simple visual relationship map. The profile changes "
                              "emphasis and explanation style, not facts."),
                input=[{"role": "user", "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)}]}],
                max_output_tokens=max(self._settings.openai_max_output_tokens, 1_200),
                text={"format": {"type": "json_schema", "name": "magifab_book_chapter", "strict": True, "schema": BookChapterResponse.model_json_schema()}},
            )
            return BookChapterResponse.model_validate_json(response.output_text)
        except PersonalizationConfigurationError:
            raise
        except Exception as error:
            raise PersonalizationProviderError("OpenAI could not create a book accessibility artifact") from error

    def _client_or_raise(self) -> OpenAI:
        if self._client: return self._client
        key = self._settings.openai_api_key.get_secret_value() if self._settings.openai_api_key else None
        if not key: raise PersonalizationConfigurationError("OPENAI_API_KEY is not configured on the backend")
        self._client = OpenAI(api_key=key)
        return self._client
