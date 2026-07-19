"""Preparation-first runtime composition; interaction only reads prepared semantic knowledge."""
import hashlib
import json
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
from schemas.personalization import GPTPersonalizationResponse
from schemas.prepared_scene_context import PreparedSceneContext
from services.accessibility_reasoning import AccessibilityReasoningEngine
from services.knowledge_expansion import KnowledgeExpansionEngine
from services.response_cache import ResponseCache
from services.reasoning_context_builder import ReasoningContextBuilder
from services.companion_response_serializer import CompanionResponseSerializer
from services.prepared_scene_context_store import PreparedSceneContextStore
from services.semantic_claim_audit import log_claims
from services.sliding_window_memory import SlidingWindowMemoryManager
from services.story_event_extractor import StoryEventExtractor
from services.story_state_manager import PreprocessingStoryBuilder
from services.timeline_memory import TimelineMemoryService
from schemas.story_state import StoryState
from schemas.interval_state import IntervalCacheMetadata, IntervalMetadata, IntervalSemanticMemory, PromptAnswer
from services.interval_state_store import IntervalStateRepository


class CompanionPipelineService:
    """Build interval snapshots during preprocessing; prompt clicks only read one."""

    def __init__(self, expansion: KnowledgeExpansionEngine, accessibility: AccessibilityReasoningEngine, response_cache: ResponseCache, settings: Settings, context_builder: ReasoningContextBuilder | None = None, serializer: CompanionResponseSerializer | None = None, prepared_contexts: PreparedSceneContextStore | None = None, memory: SlidingWindowMemoryManager | None = None, preprocessing_story: PreprocessingStoryBuilder | None = None, story_events: StoryEventExtractor | None = None, timeline_memory: TimelineMemoryService | None = None, interval_states: IntervalStateRepository | None = None):
        self._expansion = expansion
        self._accessibility = accessibility
        self._response_cache = response_cache
        self._timestamp_bucket_seconds = settings.response_cache_timestamp_bucket_seconds
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
            self._preprocessing_story.reset(request.movie_id)
            self._timeline_memory.reset(request.movie_id)
            self._interval_states.reset_movie(request.movie_id)
        expansion = self._expansion.retrieve_or_expand(KnowledgeExpansionRequest(
            movie_id=request.movie_id, interval_id=request.interval_id, catalog_scene_id=request.catalog_scene_id,
            timestamp_seconds=request.timestamp_seconds, frame_hash=frame_hash, preparation=True,
            grounding_queries=request.grounding_queries, verify_faces=request.verify_faces,
        ), image)
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
        self._logger.info("[PROMPT] generated=%d", len(interval_state.prompts.prompt_bubbles))
        self._logger.info("[PROMPT GENERATION] timestamp=%.2f generated=%d", context.timestamp_seconds, len(interval_state.prompts.prompt_bubbles))
        self._logger.info("[VISUAL DRAWER] interval=%s story_events=%d unresolved_threads=%d", request.interval_id, len(interval_state.visualDrawer.story_now), len(interval_state.storyState.unresolved_threads))
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
        return response

    def respond(self, request: CompanionPipelineRequest) -> CompanionPipelineResponse:
        """Answer from the immutable precomputed chapter; never rebuild it."""
        interval_state = self._interval_states.load(request.movie_id, request.timestamp_seconds)
        if interval_state is None:
            raise ValueError("interval_not_preprocessed")
        response, _ = self._response_cache.get_or_create(
            self._cache_key(request, self._semantic_cache_version, interval_state.metadata.interval_id, self._timestamp_bucket_seconds),
            lambda: GPTPersonalizationResponse(response=self._answer_from_scene(request.question, interval_state), model="semantic-retrieval"),
        )
        answered = interval_state.model_copy(update={"prompts": interval_state.prompts.model_copy(update={
            "prompt_answers": (PromptAnswer(prompt_id=request.question, question=request.question, answer=response.response),),
        })})
        return CompanionPipelineResponse.model_validate(answered.model_dump(mode="json"))

    def complete_preprocessing(self, request: PreprocessingCompletionRequest) -> dict[str, int | str]:
        """Validate the complete cache before it becomes available to playback."""
        summary = self._interval_states.summarize(request.movie_id, request.expected_intervals)
        if (
            summary["intervals_generated"] != request.expected_intervals
            or summary["intervals_valid"] != request.expected_intervals
        ):
            raise ValueError("movie_interval_preprocessing_incomplete")
        return summary

    @staticmethod
    def _answer_from_scene(question: str, interval_state) -> str:
        """Interaction answers are selected from the interval snapshot only."""
        cards = interval_state.characters
        if "who" in question.lower() and cards:
            return f"This is {cards[0].name}. {cards[0].reminder}"
        return interval_state.conversationContext.scene_explanation

    @staticmethod
    def _cache_key(request: CompanionPipelineRequest, cache_version: int, scene_id: str, bucket_seconds: int) -> str:
        payload = {
            "movie_id": request.movie_id, "cache_version": cache_version, "scene_id": scene_id,
            "timestamp_bucket": int(request.timestamp_seconds // bucket_seconds), "intent": request.intent.strip().lower(),
            "question": request.question.strip().lower(),
            "accessibility_profile": request.accessibility_profile.model_dump(mode="json"),
            "companion_profile": request.companion_profile.model_dump(mode="json"),
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
        return f"{request.movie_id}:v{cache_version}:{scene_id}:{digest}"

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
        active_characters=tuple(item.name for item in state.known_characters.values() if item.current_visibility),
        relationships=tuple(item.summary for item in state.known_relationships.values()),
        emotions=tuple(state.active_emotions.values()),
        important_objects=tuple(item.name for item in state.known_objects.values()),
        unresolved_threads=tuple(item.summary for item in state.open_story_threads),
        story_events=tuple(item.summary for item in state.story_so_far),
    )
