"""Static guardrails for MagiFab's observation → semantics → presentation architecture."""
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "src"


def fail(message: str) -> None:
    raise AssertionError(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    pipeline = read(BACKEND / "services" / "companion_pipeline.py")
    serializer = read(BACKEND / "services" / "companion_response_serializer.py")
    reasoner = read(BACKEND / "services" / "accessibility_reasoning.py")
    context_builder = read(BACKEND / "services" / "reasoning_context_builder.py")
    presentation_schema = read(BACKEND / "schemas" / "accessibility_presentation.py")
    response_schema = read(BACKEND / "schemas" / "companion_pipeline.py")

    for obsolete in ("def _characters", "def _objects", "def _semantic_graph", "def _prompt_bubbles", "def _serialize_prompt"):
        if obsolete in pipeline:
            fail(f"obsolete pipeline projection remains: {obsolete}")
    if pipeline.count("self._accessibility.reason(") != 2:
        fail("prepare/respond must use the same AccessibilityReasoningEngine path")
    if "AccessibilityPresentation(" not in reasoner:
        fail("AccessibilityReasoningEngine must produce AccessibilityPresentation")
    for forbidden in ("FrameObservation", "UnifiedSceneRepresentation", "SceneSummary", "raw_florence", "visible_entities"):
        if forbidden in reasoner or forbidden in context_builder:
            fail(f"reasoning boundary exposes raw perception: {forbidden}")
    for forbidden in ("Florence", "YOLO", "Grounding", "Observation", "SemanticMovieKnowledge"):
        if forbidden in serializer:
            fail(f"serializer has an internal-model dependency: {forbidden}")
    expected = {
        "scene_explanation", "prompt_bubbles", "character_cards", "relationship_summaries",
        "timeline_summary", "emotion_summaries", "vocabulary_assistance", "memory_reminders",
        "conversation_simplifications",
    }
    for field in expected:
        if field not in presentation_schema:
            fail(f"presentation DTO is missing {field}")
    for forbidden in ("perception", "semantic_graph", "semantic_matches", "detected_objects", "grounded_entities"):
        if forbidden in response_schema.split("class ScenePreparationResponse", 1)[1]:
            fail(f"public preparation response exposes {forbidden}")

    frontend_sources = "\n".join(read(path) for path in FRONTEND.rglob("*.ts*"))
    for forbidden in ("ObjectDetectionService", "VisionUnderstandingService", "semantic_matches", "semantic_graph"):
        if forbidden in frontend_sources:
            fail(f"frontend still depends on internal perception data: {forbidden}")
    print("architecture validation passed")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"architecture validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
