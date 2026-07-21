"""OpenAI reasoning boundary for extracted book chapters; it never handles video."""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from adapters.openai_personalizer import PersonalizationConfigurationError, PersonalizationProviderError
from config import Settings
from schemas.book_pipeline import BookChapterResponse


logger = logging.getLogger(__name__)


class OpenAIBookReasoner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: OpenAI | None = None

    def reason(
        self,
        chapter_number: int,
        chapter_title: str,
        section_label: str,
        page_start: int,
        page_end: int,
        text: str,
        profile: dict[str, object],
    ) -> BookChapterResponse:
        payload = {
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "section_label": section_label,
            "page_start": page_start,
            "page_end": page_end,
            "extracted_text": text[:14_000],
            "user_companion_profile": profile,
        }
        try:
            client = self._client_or_raise()
            if _supports_responses_api(client):
                response = client.responses.create(
                    model=self._settings.openai_model,
                    instructions=_book_instructions(),
                    input=[{"role": "user", "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)}]}],
                    max_output_tokens=max(self._settings.openai_max_output_tokens, 2_400),
                    text={"format": {"type": "json_schema", "name": "magifab_book_chapter", "strict": True, "schema": BookChapterResponse.model_json_schema()}},
                )
                return _validate_reasoner_payload(_extract_response_text(response), payload)

            completion = client.chat.completions.create(
                model=self._settings.openai_model,
                messages=[
                    {"role": "system", "content": _book_instructions() + " Return only valid JSON with no markdown fencing."},
                    {
                        "role": "user",
                        "content": (
                            "Use this JSON schema exactly and fill it from extracted text only.\n"
                            f"SCHEMA: {json.dumps(BookChapterResponse.model_json_schema(), ensure_ascii=False)}\n"
                            f"PAYLOAD: {json.dumps(payload, ensure_ascii=False)}"
                        ),
                    },
                ],
                max_completion_tokens=max(self._settings.openai_max_output_tokens, 2_400),
            )
            content = _extract_chat_completion_text(completion)
            return _validate_reasoner_payload(content, payload)
        except PersonalizationConfigurationError:
            raise
        except Exception as error:
            logger.exception("Book reasoning failed for chapter %s", chapter_number, exc_info=error)
            raise PersonalizationProviderError(f"OpenAI could not create a book accessibility artifact: {type(error).__name__}: {error}") from error

    def _client_or_raise(self) -> OpenAI:
        if self._client: return self._client
        key = self._settings.openai_api_key.get_secret_value() if self._settings.openai_api_key else None
        if not key: raise PersonalizationConfigurationError("OPENAI_API_KEY is not configured on the backend")
        self._client = OpenAI(api_key=key)
        return self._client


def _extract_response_text(response: object) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output_items = getattr(response, "output", None)
    if isinstance(output_items, list):
        for item in output_items:
            content_items = getattr(item, "content", None)
            if not isinstance(content_items, list):
                continue
            for content in content_items:
                text_value = getattr(content, "text", None)
                if isinstance(text_value, str) and text_value.strip():
                    return text_value

    raise ValueError("OpenAI response did not contain structured JSON output text")


def _supports_responses_api(client: OpenAI) -> bool:
    responses = getattr(client, "responses", None)
    return responses is not None and hasattr(responses, "create")


def _extract_chat_completion_text(completion: Any) -> str:
    choices = getattr(completion, "choices", None)
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenAI chat completion returned no choices")
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content
    raise ValueError("OpenAI chat completion did not contain JSON content")


def _book_instructions() -> str:
    return (
        "You create MagiFab's accessible book chapter artifacts from extracted text only. "
        "Never use outside knowledge and never invent facts not grounded in the provided extracted text. "
        "Return data that strictly matches the requested JSON schema with these goals: concise chapter summary, "
        "simple explanation adapted to the companion profile, character cards, directional relationships, "
        "important events, difficult concepts, memory aid sentence, visual relationship map nodes/edges, "
        "and three practical companion questions. Confidence must be between 0 and 1."
    )


def _validate_reasoner_payload(raw: str, payload: dict[str, object]) -> BookChapterResponse:
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        _apply_missing_defaults(parsed, payload)
    return BookChapterResponse.model_validate(parsed)


def _apply_missing_defaults(parsed: dict[str, object], payload: dict[str, object]) -> None:
    parsed.setdefault("chapter_number", payload.get("chapter_number", 1))
    parsed.setdefault("chapter_title", payload.get("chapter_title", "Untitled Chapter"))
    parsed.setdefault("section_label", payload.get("section_label", "chapter"))
    parsed.setdefault("page_start", payload.get("page_start", 1))
    parsed.setdefault("page_end", payload.get("page_end", payload.get("page_start", 1)))
    parsed.setdefault("chapter_summary", "")
    parsed.setdefault("simple_explanation", parsed.get("chapter_summary", ""))
    parsed.setdefault("characters", [])
    parsed.setdefault("relationships", [])
    parsed.setdefault("important_events", [])
    parsed.setdefault("difficult_concepts", [])
    parsed.setdefault("memory_aid", str(parsed.get("chapter_summary", ""))[:220])
    parsed.setdefault("visual_relationship_map", {"nodes": [], "edges": []})
    parsed.setdefault("companion_questions", [])
    parsed.setdefault("confidence", 0.5)
