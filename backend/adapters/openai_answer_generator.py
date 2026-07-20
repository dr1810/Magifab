"""OpenAI adapter that classifies intent and answers from retrieved evidence only."""
from __future__ import annotations

import json

from openai import OpenAI

from adapters.openai_personalizer import PersonalizationConfigurationError, PersonalizationProviderError
from config import Settings
from models.answer_generator import AnswerGenerator


class OpenAIGroundedAnswerGenerator(AnswerGenerator):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: OpenAI | None = None

    def generate(self, payload: dict[str, object]) -> dict[str, object]:
        try:
            response = self._client_or_raise().responses.create(
                model=self._settings.openai_model,
                instructions=(
                    "You are Aster, a grounded companion that has studied one complete movie or book. "
                    "Classify the user's intent naturally; do not use a fixed prompt mapping. "
                    "Answer only with the supplied retrieval context and conversation memory. "
                    "Use prior turns to resolve follow-ups. If evidence is absent, say so plainly. "
                    "Never invent scenes, identities, relationships, dialogue, emotions, causes, or future events."
                ),
                input=[{"role": "user", "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)}]}],
                max_output_tokens=self._settings.openai_max_output_tokens,
                text={"format": {"type": "json_schema", "name": "grounded_companion_answer", "strict": True, "schema": _schema()}},
            )
            result = json.loads(response.output_text)
            return result if isinstance(result, dict) else {}
        except PersonalizationConfigurationError:
            raise
        except Exception as error:
            raise PersonalizationProviderError("Unable to generate a grounded companion answer") from error

    def plan(self, payload: dict[str, object]) -> dict[str, object]:
        try:
            response = self._client_or_raise().responses.create(
                model=self._settings.openai_model,
                instructions=(
                    "You are Aster's private reasoning planner. Understand the user's natural-language question, "
                    "their learning preferences, current story position, and prior conversation. "
                    "Select only the evidence needed to answer faithfully. Do not answer the user and do not invent facts. "
                    "Intent labels are your own concise descriptions; do not map from a fixed list."
                ),
                input=[{"role": "user", "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)}]}],
                max_output_tokens=min(250, self._settings.openai_max_output_tokens),
                text={"format": {"type": "json_schema", "name": "aster_reasoning_plan", "strict": True, "schema": _plan_schema()}},
            )
            result = json.loads(response.output_text)
            return result if isinstance(result, dict) else {}
        except PersonalizationConfigurationError:
            raise
        except Exception as error:
            raise PersonalizationProviderError("Unable to plan a grounded companion answer") from error

    def _client_or_raise(self) -> OpenAI:
        if self._client:
            return self._client
        key = self._settings.openai_api_key.get_secret_value() if self._settings.openai_api_key else None
        if not key:
            raise PersonalizationConfigurationError("OPENAI_API_KEY is not configured on the backend")
        self._client = OpenAI(api_key=key)
        return self._client


def _schema() -> dict[str, object]:
    strings = {"type": "array", "items": {"type": "string"}, "maxItems": 6}
    return {"type": "object", "additionalProperties": False, "required": ["answer", "intent", "visual_aid_type", "entities", "relationships", "timeline_references", "suggested_follow_up_prompts"], "properties": {"answer": {"type": "string", "minLength": 1}, "intent": {"type": "string", "minLength": 1}, "visual_aid_type": {"type": "string", "minLength": 1}, "entities": strings, "relationships": strings, "timeline_references": strings, "suggested_follow_up_prompts": strings}}


def _plan_schema() -> dict[str, object]:
    strings = {"type": "array", "items": {"type": "string"}, "maxItems": 8}
    return {"type": "object", "additionalProperties": False, "required": ["intent", "evidence_requirements", "search_queries", "timeline_scope", "use_conversation_memory"], "properties": {"intent": {"type": "string", "minLength": 1}, "evidence_requirements": strings, "search_queries": strings, "timeline_scope": {"type": "string", "minLength": 1}, "use_conversation_memory": {"type": "boolean"}}}
