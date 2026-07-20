"""Gemini structured extraction for entity, concept, relationship, and event graphs."""
from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from adapters.openai_personalizer import PersonalizationConfigurationError, PersonalizationProviderError
from config import Settings
from models.book_semantic_extractor import BookSemanticExtractor


class GeminiBookSemanticExtractor(BookSemanticExtractor):
    def __init__(self, settings: Settings) -> None:
        self._key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        self._model = settings.gemini_model

    def extract(self, *, paragraph: str, page_number: int, chapter_title: str | None) -> dict[str, object]:
        if not self._key:
            raise PersonalizationConfigurationError("GEMINI_API_KEY is not configured on the backend")
        prompt = {"page_number": page_number, "chapter_title": chapter_title, "paragraph": paragraph}
        body = {
            "systemInstruction": {"parts": [{"text": "Extract only facts explicitly supported by the supplied book paragraph. Identify named characters, places, objects, organizations, concepts, definitions, relationships, events, and exact short quotes. Do not infer or add information."}]},
            "contents": [{"role": "user", "parts": [{"text": json.dumps(prompt, ensure_ascii=False)}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": _schema()},
        }
        request = Request(f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent", data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json", "x-goog-api-key": self._key}, method="POST")
        try:
            with urlopen(request, timeout=45) as response:
                payload = json.loads(response.read().decode("utf-8"))
            result = json.loads(payload["candidates"][0]["content"]["parts"][0]["text"])
            return result if isinstance(result, dict) else {}
        except (URLError, OSError, KeyError, IndexError, TypeError, ValueError) as error:
            raise PersonalizationProviderError("Gemini could not extract book knowledge") from error


def _schema() -> dict[str, object]:
    item = {"type": "object", "properties": {"name": {"type": "string"}, "kind": {"type": "string"}, "description": {"type": "string"}}, "required": ["name", "kind", "description"]}
    relation = {"type": "object", "properties": {"subject": {"type": "string"}, "predicate": {"type": "string"}, "object": {"type": "string"}}, "required": ["subject", "predicate", "object"]}
    definition = {"type": "object", "properties": {"term": {"type": "string"}, "definition": {"type": "string"}}, "required": ["term", "definition"]}
    return {"type": "object", "properties": {"summary": {"type": "string"}, "entities": {"type": "array", "items": item}, "relationships": {"type": "array", "items": relation}, "definitions": {"type": "array", "items": definition}, "concepts": {"type": "array", "items": item}, "events": {"type": "array", "items": {"type": "string"}}, "quotes": {"type": "array", "items": {"type": "string"}}}, "required": ["summary", "entities", "relationships", "definitions", "concepts", "events", "quotes"]}
