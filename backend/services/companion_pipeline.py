"""Preparation-first runtime composition; interaction only reads prepared semantic knowledge."""
import logging
from time import perf_counter

from PIL import Image

from config import Settings
from schemas.accessibility_reasoning import AccessibilityReasoningRequest
from schemas.companion_pipeline import (
    CompanionPipelineRequest,
    CompanionPipelineResponse,
    IntervalPreparationRequest,
    IntervalPreparationResponse,
    PreprocessingCompletionRequest,
)
from schemas.knowledge_expansion import KnowledgeExpansionRequest
from schemas.prepared_scene_context import PreparedSceneContext
from services.accessibility_reasoning import AccessibilityReasoningEngine
from services.knowledge_expansion import KnowledgeExpansionEngine
from services.reasoning_context_builder import ReasoningContextBuilder
from services.companion_response_serializer import CompanionResponseSerializer
from services.prepared_scene_context_store import PreparedSceneContextStore
from services.semantic_claim_audit import log_claims
from services.sliding_window_memory import SlidingWindowMemoryManager
from services.story_event_extractor import StoryEventExtractor
from services.story_state_manager import PreprocessingStoryBuilder
from services.timeline_memory import TimelineMemoryService
from schemas.story_state import StoryState
from schemas.interval_state import IntervalCacheMetadata, IntervalMetadata, IntervalSemanticMemory
from services.interval_state_store import IntervalStateRepository
from services.companion_answer_service import CompanionAnswerService


class CompanionPipelineService:
    """Build interval snapshots during preprocessing; prompt clicks only read one."""

    def __init__(self, expansion: KnowledgeExpansionEngine, accessibility: AccessibilityReasoningEngine, settings: Settings, context_builder: ReasoningContextBuilder | None = None, serializer: CompanionResponseSerializer | None = None, prepared_contexts: PreparedSceneContextStore | None = None, memory: SlidingWindowMemoryManager | None = None, preprocessing_story: PreprocessingStoryBuilder | None = None, story_events: StoryEventExtractor | None = None, timeline_memory: TimelineMemoryService | None = None, interval_states: IntervalStateRepository | None = None, answer_service: CompanionAnswerService | None = None):
        self._expansion = expansion
        self._accessibility = accessibility
        self._semantic_cache_version = settings.semantic_cache_version
        self._logger = logging.getLogger(__name__)
        self._context_builder = context_builder or ReasoningContextBuilder()
        self._serializer = serializer or CompanionResponseSerializer()
        self._prepared_contexts = prepared_contexts or PreparedSceneContextStore(settings.knowledge_store_dir, self._semantic_cache_version)
        self._memory = memory or SlidingWindowMemoryManager()
        self._preprocessing_story = preprocessing_story or PreprocessingStoryBuilder(settings.knowledge_store_dir, self._semantic_cache_version)
        self._story_events = story_events or StoryEventExtractor()
        self._timeline_memory = timeline_memory or TimelineMemoryService(settings.knowledge_store_dir, self._semantic_cache_version)
        self._interval_states = interval_states or IntervalStateRepository(settings.knowledge_store_dir, self._semantic_cache_version)
        self._answer_service = answer_service

    def prepare(self, request: IntervalPreparationRequest, image: Image.Image, frame_hash: str) -> IntervalPreparationResponse:
        """Analyze one interval and persist its complete immutable playback snapshot."""
        started = perf_counter()
        interval_number, start_time, end_time = self._interval_states.bounds(request.interval_start)
        if (
            request.interval_number != interval_number
            or request.interval_id != f"{request.movie_id}:interval:{interval_number}"
            or request.interval_start != start_time
            or request.interval_end != end_time
            or not start_time <= request.timestamp_seconds < end_time
        ):
            raise ValueError("invalid_fixed_interval_request")
        # A new interval-zero request begins a new preprocessing run.  This is
        # the only forward-ordered writer; the playback endpoint never touches
        # either of these mutable construction aids.
        if interval_number == 0:
            # Reset is intentionally schema-blind. No stale cache file is
            # parsed before this new preprocessing run writes interval zero.
            self._interval_states.reset_movie(request.movie_id)
            self._prepared_contexts.reset_movie(request.movie_id)
            self._expansion.reset_movie(request.movie_id)
            self._preprocessing_story.reset(request.movie_id)
            self._timeline_memory.reset(request.movie_id)
            self._logger.info("[PREPROCESSING CACHE RESET] movie=%s interval=0 complete=yes", request.movie_id)
        expansion = self._expansion.retrieve_or_expand(KnowledgeExpansionRequest(
            movie_id=request.movie_id, interval_id=request.interval_id, catalog_scene_id=request.catalog_scene_id,
            timestamp_seconds=request.timestamp_seconds, frame_hash=frame_hash, preparation=True,
            grounding_queries=request.grounding_queries, verify_faces=request.verify_faces,
        ), image)
        self._logger.info("[SEMANTIC_UPDATED] movie=%s interval=%d revision=%d source=%s", request.movie_id, interval_number, expansion.record.revision, expansion.source)
        context = self._context_builder.build(
            knowledge=expansion.record.knowledge,
            scene_id=request.interval_id,
            timestamp_seconds=request.timestamp_seconds,
            accessibility_profile=request.accessibility_profile,
        )
        reasoning_started = perf_counter()
        # The temporary builder moves only in preprocessing order. Its state
        # is snapshotted even when vision/catalog data is quiet.
        memory_update = self._memory.update(context, frame_hash=frame_hash)
        previous_state = self._preprocessing_story.get(request.movie_id)
        story_events = self._story_events.extract(context, previous_state)
        state_changes = [event for event in story_events if event.requires_memory]
        state_update = self._preprocessing_story.advance(request.movie_id, request.interval_id, request.timestamp_seconds, state_changes)
        active_story_state = state_update.state
        self._logger.info("[MEMORY_UPDATED] movie=%s interval=%d active_characters=%d events=%d", request.movie_id, interval_number, len(active_story_state.known_characters), len(active_story_state.story_so_far))
        timeline_state = self._timeline_memory.write_interval(
            previous_state, active_story_state, state_changes,
            interval_id=request.interval_id, interval_start=start_time, interval_end=end_time,
        )
        prepared_context = self._prepared_contexts.save(PreparedSceneContext(
            movie_id=request.movie_id, interval_id=request.interval_id, timestamp_seconds=request.timestamp_seconds,
            preparation_cache_key=expansion.cache_key, semantic_cache_version=self._semantic_cache_version,
            knowledge_revision=expansion.record.revision, knowledge_source=expansion.source,
            semantic_map_cached=expansion.source == "retrieved", reasoning_cached=False,
            frame_hash=frame_hash, reasoning_context=context,
        ))
        log_claims("PreparedSceneContext.saved", prepared_context.reasoning_context.semantic_scene, movie_id=request.movie_id, scene_id=context.scene_id)
        self._logger.info("[TRACE][PREPARED_CONTEXT] saved=yes cache_key=%s semantic_claims=%d active_characters=%d reused=%s", prepared_context.preparation_cache_key, len(context.semantic_scene), len(context.active_characters), expansion.source == "retrieved")
        interval_state = self._accessibility.reason(AccessibilityReasoningRequest(
            story_state=active_story_state,
            timeline_state=timeline_state,
            accessibility_profile=request.accessibility_profile,
            companion_profile=request.companion_profile,
        ), knowledge_revision=expansion.record.revision)
        # Preparation owns the fixed playback chapter boundary.  The semantic
        # timestamp used above remains available to the internal story engine.
        interval_state = interval_state.model_copy(update={"metadata": IntervalMetadata(
            interval_id=request.interval_id, catalog_scene_id=request.catalog_scene_id,
            movie_id=request.movie_id, start_time=start_time, end_time=end_time,
            interval_number=interval_number, knowledge_revision=expansion.record.revision,
        ), "semanticMemoryBefore": _memory_checkpoint(previous_state),
            "semanticMemoryAfter": _memory_checkpoint(active_story_state),
            "cacheMetadata": IntervalCacheMetadata(
                semantic_cache_key=expansion.cache_key, knowledge_source=expansion.source,
                semantic_map_cached=expansion.source == "retrieved", frame_hash=frame_hash,
            )})
        self._interval_states.save(interval_state)
        self._logger.info("[INTERVAL_CACHE_UPDATED] movie=%s interval=%d", request.movie_id, interval_number)
        self._logger.info("[PROMPTS_GENERATED] movie=%s interval=%d count=%d", request.movie_id, interval_number, len(interval_state.prompts.prompt_bubbles))
        self._logger.info("[PROMPTS_UPDATED] movie=%s interval=%d count=%d", request.movie_id, interval_number, len(interval_state.prompts.prompt_bubbles))
        self._logger.info("[DRAWER_GENERATED] movie=%s interval=%d story_now=%d relationships=%d timeline=%d objects=%d memory=%d", request.movie_id, interval_number, len(interval_state.visualDrawer.story_now), len(interval_state.visualDrawer.relationships), len(interval_state.visualDrawer.timeline), len(interval_state.visualDrawer.objects), len(interval_state.visualDrawer.memory))
        self._logger.info("[DRAWER_UPDATED] movie=%s interval=%d", request.movie_id, interval_number)
        self._log_timeline_resolution(request.movie_id, context.timestamp_seconds, timeline_state, interval_state)
        self._logger.info("[TRACE][REASONING_ENGINE] executed=yes movie=%s interval=%s frame_hash=%s reasoning_rebuilt=yes output_prompts=%d character_cards=%d duration_ms=%.1f", request.movie_id, request.interval_id, frame_hash, len(interval_state.prompts.prompt_bubbles), len(interval_state.characters), (perf_counter() - reasoning_started) * 1000)
        response = self._serializer.prepare(
            interval_state=interval_state,
        )
        self._logger.info(
            "[TRACE][RESPONSE_ASSEMBLY] executed=yes response_prompt_count=%d response_prompt_list_id=%s first_prompt=%s nested_prompt_count=%d nested_prompt_list_id=%s nested_first=%s",
            len(response.prompts.prompt_bubbles), id(response.prompts.prompt_bubbles), response.prompts.prompt_bubbles[0].label if response.prompts.prompt_bubbles else None,
            len(response.prompts.prompt_bubbles), id(response.prompts.prompt_bubbles), response.prompts.prompt_bubbles[0].label if response.prompts.prompt_bubbles else None,
        )
        self._logger.info("[TRACE][PREPARE_SERVICE] complete source=%s duration_ms=%.1f", expansion.source, (perf_counter() - started) * 1000)
        self._logger.info("[INTERVAL_COMPLETED] movie=%s interval=%d duration_ms=%.1f", request.movie_id, interval_number, (perf_counter() - started) * 1000)
        return response

    def respond(self, request: CompanionPipelineRequest) -> CompanionPipelineResponse:
        """Answer from the immutable precomputed chapter; never rebuild it."""
        interval_state = self._interval_states.load(request.movie_id, request.timestamp_seconds)
        if interval_state is None:
            raise ValueError("interval_not_preprocessed")
        if self._answer_service is None:
            raise RuntimeError("grounded_answer_service_not_configured")
        answered = self._answer_service.answer(request, interval_state)
        return CompanionPipelineResponse.model_validate(answered.model_dump(mode="json"))

    def complete_preprocessing(self, request: PreprocessingCompletionRequest) -> dict[str, int | str | bool]:
        """Validate the complete cache before it becomes available to playback."""
        self._interval_states.finalize_movie(request.movie_id)
        summary = self._interval_states.summarize(request.movie_id, request.expected_intervals)
        if (
            summary["intervals_generated"] != request.expected_intervals
            or summary["intervals_valid"] != request.expected_intervals
        ):
            raise ValueError("movie_interval_preprocessing_incomplete")
        if self._answer_service is None:
            raise RuntimeError("grounded_answer_service_not_configured")
        self._answer_service.preprocess_work(request.movie_id)
        return summary

    def _log_timeline_resolution(self, movie_id, timestamp, timeline_state, interval_state) -> None:
        memory = self._timeline_memory.get(movie_id)
        self._logger.info(
            "[TIMELINE RESOLUTION] movie=%s timestamp=%.2f resolved=%s revision=%d prompts=%d characters=%d events=%d relationships=%d drawer=%s",
            movie_id, timestamp, timeline_state.timestamp if timeline_state else None, len(memory.intervals),
            len(interval_state.prompts.prompt_bubbles), len(interval_state.characters),
            len(interval_state.visualDrawer.story_now), len(interval_state.relationships),
            bool(interval_state.visualDrawer),
        )


def _memory_checkpoint(state: StoryState) -> IntervalSemanticMemory:
    """Serialize only durable story memory into an immutable interval field."""
    return IntervalSemanticMemory(
        active_characters=_unique_text(item.name for item in state.known_characters.values() if item.current_visibility),
        relationships=_unique_text(item.summary for item in state.known_relationships.values()),
        emotions=_unique_text(state.active_emotions.values()),
        important_objects=_unique_text(item.name for item in state.known_objects.values()),
        unresolved_threads=_unique_text(item.summary for item in state.open_story_threads),
        story_events=_unique_text(item.summary for item in state.story_so_far),
    )


def _unique_text(values) -> tuple[str, ...]:
    """Normalize snapshot collections once before immutable serialization."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(value.split()) if isinstance(value, str) else ""
        if cleaned and cleaned.casefold() not in seen:
            seen.add(cleaned.casefold())
            result.append(cleaned)
    return tuple(result)
