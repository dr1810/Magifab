"""Gemini File API adapter. Gemini receives a complete clip, never extracted frames."""
from __future__ import annotations

import json
from pathlib import Path
import time

from config import Settings
from models.movie_pipeline import VideoVisualProvider
from schemas.movie_pipeline import GeminiVisualScene


class GeminiVideoConfigurationError(RuntimeError):
    pass


class GeminiVideoProvider(VideoVisualProvider):
    def __init__(self, settings: Settings) -> None:
        self._key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        self._model = settings.gemini_model
        self._client = None

    def analyze(self, video_path: Path, *, start_seconds: float, end_seconds: float) -> GeminiVisualScene:
        client = self._client_or_raise()
        uploaded = client.files.upload(file=str(video_path), config={"mime_type": "video/mp4"})
        try:
            deadline = time.monotonic() + 900
            while _state_name(uploaded) == "PROCESSING":
                if time.monotonic() >= deadline:
                    raise TimeoutError("gemini_video_file_processing_timed_out")
                time.sleep(5)
                uploaded = client.files.get(name=uploaded.name)
            if _state_name(uploaded) != "ACTIVE":
                raise RuntimeError(f"gemini_video_file_not_active:{_state_name(uploaded)}")
            response = client.models.generate_content(
                model=self._model,
                contents=[uploaded, _visual_prompt(start_seconds, end_seconds)],
                config={"response_mime_type": "application/json", "response_json_schema": GeminiVisualScene.model_json_schema()},
            )
            return GeminiVisualScene.model_validate(_parse_json(getattr(response, "text", "")))
        finally:
            # Remote clip retention is unnecessary after its local canonical record is saved.
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass

    def _client_or_raise(self):
        if not self._key:
            raise GeminiVideoConfigurationError("GEMINI_API_KEY is not configured on the backend")
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self._key)
        return self._client


def _state_name(uploaded: object) -> str:
    state = getattr(uploaded, "state", None)
    return str(getattr(state, "name", state or "")).upper()


def _parse_json(value: str) -> dict[str, object]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("gemini_did_not_return_a_json_object")
    return parsed


def _visual_prompt(start_seconds: float, end_seconds: float) -> str:
    return f"""You are MagiFab's visual-understanding stage. Analyze this entire continuous video clip from approximately {start_seconds:.1f}s to {end_seconds:.1f}s; do not analyze sampled frames. Return only the requested JSON.

Your responsibility is visual observation only. Do not use outside movie knowledge, infer a film title, identify a person from resemblance, explain accessibility needs, or add reasoning. Never invent names. Use `Unknown` and `low` certainty whenever visual evidence cannot establish an identity. Only include timestamps that the clip supports. `entities_needing_identification` must include only an actually unresolved character, creature, landmark, movie title, object with text, organization, book, or historical person; do not include generic scenery or ordinary actions."""
