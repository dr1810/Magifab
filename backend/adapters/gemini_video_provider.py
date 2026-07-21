"""Gemini File API adapter. Gemini receives a complete clip, never extracted frames."""
from __future__ import annotations

import json
from pathlib import Path

from config import Settings
from models.movie_pipeline import VideoVisualProvider
from schemas.movie_pipeline import GeminiVisualScene
from services.gemini_client import GeminiClient


class GeminiVideoConfigurationError(RuntimeError):
    pass


class GeminiVideoProvider(VideoVisualProvider):
    def __init__(self, settings: Settings, gemini_client: GeminiClient | None = None) -> None:
        self._model = settings.gemini_model
        self._gemini = gemini_client or GeminiClient.from_settings(settings)

    def analyze(self, video_path: Path, *, start_seconds: float, end_seconds: float) -> GeminiVisualScene:
        uploaded = self._gemini.upload_video(video_path)
        try:
            uploaded = self._gemini.wait_until_active(uploaded)
            if _state_name(uploaded) != "ACTIVE":
                raise RuntimeError(f"gemini_video_file_not_active:{_state_name(uploaded)}")
            response = self._gemini.analyze_video_json(
                uploaded=uploaded,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                response_json_schema=GeminiVisualScene.model_json_schema(),
                model=self._model,
            )
            return GeminiVisualScene.model_validate(_parse_json(getattr(response, "text", "")))
        finally:
            # Remote clip retention is unnecessary after its local canonical record is saved.
            self._gemini.delete_file(uploaded)


def _state_name(uploaded: object) -> str:
    state = getattr(uploaded, "state", None)
    return str(getattr(state, "name", state or "")).upper()


def _parse_json(value: str) -> dict[str, object]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("gemini_did_not_return_a_json_object")
    return parsed


def _visual_prompt(start_seconds: float, end_seconds: float) -> str:
    # Kept for compatibility with older tests/tools that import this symbol.
    from services.gemini_client import _visual_prompt as shared_visual_prompt

    return shared_visual_prompt(start_seconds, end_seconds)
