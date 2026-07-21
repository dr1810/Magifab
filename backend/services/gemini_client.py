"""Shared google-genai client helpers for MagiFab backend services."""
from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from config import Settings


class GeminiClientConfigurationError(RuntimeError):
    pass


def _load_sdk() -> tuple[Any, Any]:
    try:
        from google import genai
        from google.genai import types
    except Exception as error:
        raise GeminiClientConfigurationError(
            "Failed to import google-genai SDK. Install dependencies with `pip install -r backend/requirements.txt` "
            "or `pip install google-genai`."
        ) from error
    return genai, types


def validate_gemini_sdk_import() -> None:
    _load_sdk()


def get_genai_types() -> Any:
    _, types = _load_sdk()
    return types


class GeminiClient:
    def __init__(self, *, api_key: str | None, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client: Any | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "GeminiClient":
        key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        return cls(api_key=key, model=settings.gemini_model)

    def client_or_raise(self) -> Any:
        if not self._api_key:
            raise GeminiClientConfigurationError("GEMINI_API_KEY is not configured on the backend")
        if self._client is None:
            genai, _ = _load_sdk()
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def upload_video(self, video_path: Path, *, mime_type: str = "video/mp4") -> Any:
        return self.client_or_raise().files.upload(file=str(video_path), config={"mime_type": mime_type})

    def wait_until_active(self, uploaded: Any, *, timeout_seconds: int = 900, poll_seconds: int = 5) -> Any:
        deadline = time.monotonic() + timeout_seconds
        current = uploaded
        while _state_name(current) == "PROCESSING":
            if time.monotonic() >= deadline:
                raise TimeoutError("gemini_video_file_processing_timed_out")
            time.sleep(poll_seconds)
            current = self.client_or_raise().files.get(name=current.name)
        return current

    def delete_file(self, uploaded: Any) -> None:
        try:
            self.client_or_raise().files.delete(name=uploaded.name)
        except Exception:
            pass

    def analyze_video_json(self, *, uploaded: Any, start_seconds: float, end_seconds: float, response_json_schema: dict[str, object], model: str | None = None) -> Any:
        return self.client_or_raise().models.generate_content(
            model=model or self._model,
            contents=[uploaded, _visual_prompt(start_seconds, end_seconds)],
            config={"response_mime_type": "application/json", "response_json_schema": response_json_schema},
        )


def _state_name(uploaded: object) -> str:
    state = getattr(uploaded, "state", None)
    return str(getattr(state, "name", state or "")).upper()


def _visual_prompt(start_seconds: float, end_seconds: float) -> str:
    return f"""You are MagiFab's visual-understanding stage. Analyze this entire continuous video clip from approximately {start_seconds:.1f}s to {end_seconds:.1f}s; do not analyze sampled frames. Return only the requested JSON.

Your responsibility is visual observation only. Do not use outside movie knowledge, infer a film title, identify a person from resemblance, explain accessibility needs, or add reasoning. Never invent names. Use `Unknown` and `low` certainty whenever visual evidence cannot establish an identity. Only include timestamps that the clip supports. `entities_needing_identification` must include only an actually unresolved character, creature, landmark, movie title, object with text, organization, book, or historical person; do not include generic scenery or ordinary actions."""