"""OpenAI Responses API adapter for GPT-5.6 language personalization only."""
import json
import logging

from openai import OpenAI

from config import Settings
from models.language_personalizer import LanguagePersonalizer
from schemas.personalization import GPTPersonalizationRequest

logger = logging.getLogger(__name__)


class PersonalizationConfigurationError(RuntimeError):
    """Raised when the server-side OpenAI credentials have not been configured."""


class PersonalizationProviderError(RuntimeError):
    """Raised when OpenAI cannot produce a valid structured language response."""


class OpenAIGPTPersonalizer(LanguagePersonalizer):
    """GPT-5.6 adapter that has access only to structured semantic and accessibility facts."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: OpenAI | None = None

    def personalize(self, request: GPTPersonalizationRequest) -> tuple[str, str]:
        client = self._get_client()
        try:
            response = client.responses.create(
                model=self._settings.openai_model,
                instructions=_instructions(),
                input=[{
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(request.model_dump(mode="json"), ensure_ascii=False)}],
                }],
                max_output_tokens=self._settings.openai_max_output_tokens,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "accessible_personalized_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["response"],
                            "properties": {"response": {"type": "string", "minLength": 1}},
                        },
                    },
                },
            )
            payload = json.loads(response.output_text)
            text = payload.get("response") if isinstance(payload, dict) else None
            if not isinstance(text, str) or not text.strip():
                raise PersonalizationProviderError("OpenAI returned an invalid personalization response")
            return text.strip(), self._settings.openai_model
        except PersonalizationProviderError:
            raise
        except Exception as error:
            logger.exception("OpenAI personalization request failed", extra={"model": self._settings.openai_model})
            raise PersonalizationProviderError("Unable to create a personalized response") from error

    def _get_client(self) -> OpenAI:
        if self._client is not None:
            return self._client
        key = self._settings.openai_api_key.get_secret_value() if self._settings.openai_api_key else None
        if not key:
            raise PersonalizationConfigurationError("OPENAI_API_KEY is not configured on the backend")
        self._client = OpenAI(api_key=key)
        return self._client


def _instructions() -> str:
    return " ".join((
        "You are MagiFab's accessibility language companion.",
        "Turn only the supplied structured semantic facts and accessibility content into clear, kind, simple language.",
        "Personalize wording to the supplied accessibility and companion profiles.",
        "Do not identify characters, detect objects, inspect images, match entities, infer relationships, infer emotions, or add plot facts.",
        "Do not redo backend reasoning. Treat every fact not present in the structured input as unknown.",
        "If the user's question needs an absent fact, say simply that the information is not available yet.",
        "Keep the response concise and easy to understand.",
    ))
