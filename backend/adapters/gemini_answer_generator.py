"""Gemini structured planner and grounded-answer adapter."""
from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from adapters.openai_personalizer import PersonalizationConfigurationError, PersonalizationProviderError
from config import Settings
from models.answer_generator import AnswerGenerator


class GeminiGroundedAnswerGenerator(AnswerGenerator):
    def __init__(self, settings: Settings) -> None:
        self._key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        self._model = settings.gemini_model

    def plan(self, payload: dict[str, object]) -> dict[str, object]:
        return self._generate(
            "You are Aster's retrieval planner. Infer the question intent without a fixed keyword map. "
            "Choose only the needed semantic evidence types and short retrieval queries. Do not answer the question or invent facts.",
            payload,
            _plan_schema(),
        )

    def generate(self, payload: dict[str, object]) -> dict[str, object]:
        return self._generate(
            "You are Aster, a grounded companion. Answer using only the retrieved evidence chunks and conversation memory. "
            "Each chunk is a source excerpt; do not claim facts absent from them. If evidence is insufficient, state that clearly. "
            "Adapt wording to the supplied personal memory. Choose the most useful visual aid type yourself and offer relevant follow-ups.",
            payload,
            _answer_schema(),
        )

    def _generate(self, instructions: str, payload: dict[str, object], schema: dict[str, object]) -> dict[str, object]:
        if not self._key:
            raise PersonalizationConfigurationError("GEMINI_API_KEY is not configured on the backend")
        request_payload = {
            "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"
        request = Request(url, data=json.dumps(request_payload).encode("utf-8"), headers={"Content-Type": "application/json", "x-goog-api-key": self._key}, method="POST")
        try:
            with urlopen(request, timeout=45) as response:
                body = json.loads(response.read().decode("utf-8"))
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(text)
            return result if isinstance(result, dict) else {}
        except (URLError, OSError, KeyError, IndexError, TypeError, ValueError) as error:
            raise PersonalizationProviderError("Gemini could not produce a grounded answer") from error


def _strings() -> dict[str, object]:
    return {"type": "array", "items": {"type": "string"}, "maxItems": 8}


def _plan_schema() -> dict[str, object]:
    strings = _strings()
    return {"type": "object", "properties": {"intent": {"type": "string"}, "evidence_requirements": strings, "search_queries": strings, "timeline_scope": {"type": "string"}, "use_conversation_memory": {"type": "boolean"}}, "required": ["intent", "evidence_requirements", "search_queries", "timeline_scope", "use_conversation_memory"]}


def _answer_schema() -> dict[str, object]:
    strings = _strings()
    return {"type": "object", "properties": {"answer": {"type": "string"}, "intent": {"type": "string"}, "visual_aid_type": {"type": "string"}, "entities": strings, "relationships": strings, "timeline_references": strings, "suggested_follow_up_prompts": strings}, "required": ["answer", "intent", "visual_aid_type", "entities", "relationships", "timeline_references", "suggested_follow_up_prompts"]}
