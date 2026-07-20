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
    prepared_context_store = read(BACKEND / "services" / "prepared_scene_context_store.py")
    preprocessing_builder = read(BACKEND / "services" / "story_state_manager.py")
    event_extractor = read(BACKEND / "services" / "story_event_extractor.py")
    timeline_memory = read(BACKEND / "services" / "timeline_memory.py")
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
    if "interval_seconds: int = 30" not in repository:
        fail("IntervalStateRepository must use fixed 30-second chapters")
    reset_source = repository.split("def reset_movie", 1)[1].split("def finalize_movie", 1)[0]
    if "model_validate" in reset_source:
        fail("IntervalState cache reset must not deserialize stale snapshots")
    prepared_reset = prepared_context_store.split("def reset_movie", 1)[1].split("def _path", 1)[0]
    if "model_validate" in prepared_reset:
        fail("prepared-context reset must not deserialize stale snapshots")
    for reset_call in ("self._interval_states.reset_movie", "self._prepared_contexts.reset_movie", "self._expansion.reset_movie", "self._preprocessing_story.reset", "self._timeline_memory.reset", "self._response_cache.clear"):
        if reset_call not in pipeline:
            fail(f"preprocessing reset is missing cache owner: {reset_call}")
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
    if "seen_triggers" in timeline_memory or "seen_intervals" not in timeline_memory:
        fail("quiet fixed intervals must not be deduplicated by an empty trigger set")
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
    expected = {"metadata", "prompts", "visualDrawer", "storyState", "characters", "relationships", "memory", "conversationContext", "accessibilityHints", "semanticMemoryBefore", "semanticMemoryAfter", "timelineMemory", "cacheMetadata"}
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
    for required_log in ("[INTERVAL_CREATED]", "[INTERVAL_COMPLETED]", "[PROMPTS_GENERATED]", "[DRAWER_GENERATED]", "[MEMORY_UPDATED]", "[SEMANTIC_UPDATED]"):
        if required_log not in pipeline and required_log not in repository:
            fail(f"interval lifecycle log is missing: {required_log}")
    if "Math.floor(timestamp / INTERVAL_SECONDS)" not in frontend_viewer or not any(
        expression in frontend_viewer
        for expression in ("Math.ceil(duration / INTERVAL_SECONDS)", "Math.ceil(preprocessingDuration / INTERVAL_SECONDS)")
    ):
        fail("frontend playback and preprocessing must use fixed 30-second intervals")
    playback_loader = frontend_viewer.split("const loadIntervalState", 1)[1].split("useEffect(() => {", 1)[0]
    for forbidden in ("companionBackendService", "getScene(", "prepareInterval", "respond("):
        if forbidden in playback_loader:
            fail(f"playback loader must restore snapshots only: {forbidden}")
    if "preloadAdjacentSnapshots" not in playback_loader:
        fail("playback loader must preload immutable adjacent snapshots")

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
