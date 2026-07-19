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
    expansion = read(BACKEND / "services" / "knowledge_expansion.py")
    graph_builder = read(BACKEND / "services" / "semantic_graph_builder.py")
    provider = read(BACKEND / "services" / "movie_knowledge_provider.py")
    interval_schema = read(BACKEND / "schemas" / "interval_state.py")
    response_schema = read(BACKEND / "schemas" / "companion_pipeline.py")
    repository = read(BACKEND / "services" / "interval_state_store.py")
    preprocessing_builder = read(BACKEND / "services" / "story_state_manager.py")
    event_extractor = read(BACKEND / "services" / "story_event_extractor.py")
    frontend_viewer = read(FRONTEND / "movie-viewer.tsx")

    for obsolete in ("def _characters", "def _objects", "def _semantic_graph", "def _prompt_bubbles", "def _serialize_prompt"):
        if obsolete in pipeline:
            fail(f"obsolete pipeline projection remains: {obsolete}")
    if pipeline.count("self._accessibility.reason(") != 1:
        fail("IntervalState may only be assembled during preprocessing")
    respond_source = pipeline.split("def respond", 1)[1]
    if "self._interval_states.load(" not in respond_source:
        fail("prompt responses must load the stored IntervalState")
    if "self._accessibility.reason(" in respond_source:
        fail("prompt responses must not regenerate IntervalState")
    if "_preprocessing_story" in respond_source or "_timeline_memory.at(" in respond_source:
        fail("playback response must not touch mutable preprocessing state")
    if "StoryStateManager" in preprocessing_builder or "timestamp regressed" in preprocessing_builder:
        fail("legacy forward-only StoryStateManager remains")
    if "class IntervalStateRepository" not in repository or "def load(" not in repository:
        fail("IntervalStateRepository must own runtime snapshot retrieval")
    if "interval_seconds: int = 10" not in repository:
        fail("IntervalStateRepository must use fixed 10-second chapters")
    for required_log in ("[INTERVAL_VALIDATED]", "[MOVIE PREPROCESSING SUMMARY]"):
        if required_log not in repository:
            fail(f"preprocessing validation log is missing: {required_log}")
    if "[INTERVAL_CATALOG_COVERAGE]" not in expansion:
        fail("preprocessing must trace catalog coverage for every interval")
    if "timeline_active" not in expansion or "timeline_active" not in read(BACKEND / "services" / "semantic_matching.py"):
        fail("catalog continuity must be applied generically in expansion and matching")
    if "request.interval_id" not in expansion or "catalog_scene_id" not in expansion:
        fail("interval identity must own semantic expansion; catalog scenes may only enrich it")
    if "character_left" in event_extractor:
        fail("sample absence must not create a character-left story event")
    if "IntervalState(" not in reasoner:
        fail("AccessibilityReasoningEngine must produce IntervalState")
    if "MovieKnowledgeProvider" not in expansion or "self._movie_knowledge_provider.get" not in expansion:
        fail("knowledge expansion must retrieve the movie catalog before perception")
    if "evidence_origin" not in graph_builder or "knowledge_ids" not in graph_builder:
        fail("semantic graph claims must retain perception/catalog provenance")
    if "model_copy(deep=True)" not in provider:
        fail("movie catalog provider must isolate cached catalog instances")
    for forbidden in ("FrameObservation", "UnifiedSceneRepresentation", "SceneSummary", "raw_florence", "visible_entities"):
        if forbidden in reasoner or forbidden in context_builder:
            fail(f"reasoning boundary exposes raw perception: {forbidden}")
    for forbidden in ("Florence", "YOLO", "Grounding", "Observation", "SemanticMovieKnowledge"):
        if forbidden in serializer:
            fail(f"serializer has an internal-model dependency: {forbidden}")
    expected = {"metadata", "prompts", "visualDrawer", "storyState", "characters", "relationships", "memory", "conversationContext", "accessibilityHints", "semanticMemoryBefore", "semanticMemoryAfter", "cacheMetadata"}
    for field in expected:
        if field not in interval_schema:
            fail(f"IntervalState DTO is missing {field}")
    if "frozen=True" not in interval_schema:
        fail("IntervalState must be immutable")
    for legacy in ("presentation:", "character_cards:", "relationship_summaries:", "timeline_summary:", "AccessibilityDrawerContent", "LiveStoryAssistant"):
        if legacy in response_schema:
            fail(f"public response retains fragmented field: {legacy}")
    preparation_contract = response_schema.split("class IntervalPreparationResponse", 1)[1]
    for forbidden in ("perception", "semantic_graph", "semantic_matches", "detected_objects", "grounded_entities"):
        if forbidden in preparation_contract:
            fail(f"public preparation response exposes {forbidden}")
    if "scene_id" in preparation_contract:
        fail("interval preparation contract must not expose a runtime scene id")
    if "Math.floor(timestamp / 10)" not in frontend_viewer or "Math.ceil(duration / 10)" not in frontend_viewer:
        fail("frontend playback and preprocessing must use fixed 10-second intervals")

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
