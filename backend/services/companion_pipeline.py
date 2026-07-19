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
    PreparationCacheMetadata,
    ScenePreparationRequest,
    ScenePreparationResponse,
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
from services.story_state_manager import StoryStateManager
from services.timeline_memory import TimelineMemoryService
from schemas.story_state import StoryState


class CompanionPipelineService:
    """Build scene knowledge during preparation; never invoke perception or GPT after a prompt click."""

    def __init__(self, expansion: KnowledgeExpansionEngine, accessibility: AccessibilityReasoningEngine, response_cache: ResponseCache, settings: Settings, context_builder: ReasoningContextBuilder | None = None, serializer: CompanionResponseSerializer | None = None, prepared_contexts: PreparedSceneContextStore | None = None, memory: SlidingWindowMemoryManager | None = None, story_state: StoryStateManager | None = None, story_events: StoryEventExtractor | None = None, timeline_memory: TimelineMemoryService | None = None):
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
        self._story_state = story_state or StoryStateManager(settings.knowledge_store_dir, self._semantic_cache_version)
        self._story_events = story_events or StoryEventExtractor()
        self._timeline_memory = timeline_memory or TimelineMemoryService(settings.knowledge_store_dir, self._semantic_cache_version)

    def prepare(self, request: ScenePreparationRequest, image: Image.Image, frame_hash: str) -> ScenePreparationResponse:
        """Explore one representative unknown scene and persist all reusable observations."""
        started = perf_counter()
        expansion = self._expansion.retrieve_or_expand(KnowledgeExpansionRequest(
            movie_id=request.movie_id, scene_id=request.scene_id, timestamp_seconds=request.timestamp_seconds, frame_hash=frame_hash, preparation=True,
            grounding_queries=request.grounding_queries, verify_faces=request.verify_faces,
        ), image)
        context = self._context_builder.build(
            knowledge=expansion.record.knowledge,
            scene_id=expansion.scene_summary.scene_id if expansion.scene_summary else request.scene_id,
            timestamp_seconds=request.timestamp_seconds,
            accessibility_profile=request.accessibility_profile,
        )
        reasoning_started = perf_counter()
        # Windows provide a bounded observation and attention signal only.
        # StoryStateManager is the only durable narrative owner.
        memory_update = self._memory.update(context, frame_hash=frame_hash)
        previous_state = self._story_state.get(request.movie_id)
        story_events = self._story_events.extract(context, previous_state)
        # Windows are observation-only. A timeline interval is persisted only
        # when semantic information creates a new StoryEvent.
        state_changes = [event for event in story_events if event.requires_memory]
        if state_changes:
            state_update = self._story_state.update(request.movie_id, context.scene_id, context.timestamp_seconds, state_changes)
            active_story_state = state_update.state
            self._timeline_memory.write_change(previous_state, active_story_state, state_changes)
            timeline_state = self._timeline_memory.at(request.movie_id, context.timestamp_seconds)
        else:
            timeline_state = self._timeline_memory.at(request.movie_id, context.timestamp_seconds)
            active_story_state = timeline_state.story_state if timeline_state is not None else StoryState(movie_id=request.movie_id, current_timestamp=request.timestamp_seconds)
        prepared_context = self._prepared_contexts.save(PreparedSceneContext(
            movie_id=request.movie_id, scene_id=context.scene_id, timestamp_seconds=request.timestamp_seconds,
            preparation_cache_key=expansion.cache_key, semantic_cache_version=self._semantic_cache_version,
            knowledge_revision=expansion.record.revision, knowledge_source=expansion.source,
            semantic_map_cached=expansion.source == "retrieved", reasoning_cached=False,
            frame_hash=frame_hash, reasoning_context=context,
        ))
        log_claims("PreparedSceneContext.saved", prepared_context.reasoning_context.semantic_scene, movie_id=request.movie_id, scene_id=context.scene_id)
        self._logger.info("[TRACE][PREPARED_CONTEXT] saved=yes cache_key=%s semantic_claims=%d active_characters=%d reused=%s", prepared_context.preparation_cache_key, len(context.semantic_scene), len(context.active_characters), expansion.source == "retrieved")
        presentation = self._accessibility.reason(AccessibilityReasoningRequest(
            story_state=active_story_state,
            timeline_state=timeline_state,
            accessibility_profile=request.accessibility_profile,
            companion_profile=request.companion_profile,
        ))
        self._story_state.record_prompts(request.movie_id, context.timestamp_seconds, [prompt.id.removeprefix("prompt:") for prompt in presentation.prompt_bubbles if prompt.id.startswith("prompt:")])
        self._logger.info("[PROMPT] generated=%d", len(presentation.prompt_bubbles))
        self._logger.info("[PROMPT GENERATION] timestamp=%.2f generated=%d", context.timestamp_seconds, len(presentation.prompt_bubbles))
        self._logger.info("[VISUAL DRAWER] scene=%s story_events=%d unresolved_threads=%d", context.scene_id, len(presentation.live_story.recent_events) if presentation.live_story else 0, len(presentation.live_story.unresolved_story_threads) if presentation.live_story else 0)
        self._log_timeline_resolution(request.movie_id, context.timestamp_seconds, timeline_state, presentation)
        self._logger.info("[TRACE][REASONING_ENGINE] executed=yes movie=%s scene=%s frame_hash=%s reasoning_rebuilt=yes output_prompts=%d character_cards=%d duration_ms=%.1f", request.movie_id, request.scene_id, frame_hash, len(presentation.prompt_bubbles), len(presentation.character_cards), (perf_counter() - reasoning_started) * 1000)
        response = self._serializer.prepare(
            presentation=presentation,
            knowledge_source=expansion.source,
            knowledge_revision=expansion.record.revision,
            cache=PreparationCacheMetadata(
                cache_key=expansion.cache_key,
                knowledge_revision=expansion.record.revision,
                knowledge_source=expansion.source,
                semantic_map_cached=expansion.source == "retrieved",
                frame_hash=frame_hash,
                # Preparation always re-runs deterministic reasoning over the
                # current semantic map; it never reads a reasoning response.
                reasoning_cached=False,
            ),
        )
        self._logger.info(
            "[TRACE][RESPONSE_ASSEMBLY] executed=yes response_prompt_count=%d response_prompt_list_id=%s first_prompt=%s nested_prompt_count=%d nested_prompt_list_id=%s nested_first=%s",
            len(response.presentation.prompt_bubbles), id(response.presentation.prompt_bubbles), response.presentation.prompt_bubbles[0].label if response.presentation.prompt_bubbles else None,
            len(response.presentation.prompt_bubbles), id(response.presentation.prompt_bubbles), response.presentation.prompt_bubbles[0].label if response.presentation.prompt_bubbles else None,
        )
        self._logger.info("[TRACE][PREPARE_SERVICE] complete source=%s duration_ms=%.1f", expansion.source, (perf_counter() - started) * 1000)
        return response

    def respond(self, request: CompanionPipelineRequest) -> CompanionPipelineResponse:
        """Serve an instant answer from prepared facts; a miss is explicit and never triggers models."""
        prepared = self._prepared_contexts.load(
            movie_id=request.movie_id,
            scene_id=request.scene_id,
            timestamp_seconds=request.timestamp_seconds,
            max_delta_seconds=self._timestamp_bucket_seconds,
        )
        if prepared is not None:
            context = prepared.reasoning_context
            knowledge_revision = prepared.knowledge_revision
            scene_id = context.scene_id
            knowledge_source = "retrieved"
            self._logger.info(
                "[TRACE][PREPARED_CONTEXT] loaded=yes cache_hit=yes cache_key=%s semantic_claims=%d active_characters=%d reused=yes rebuilt=no",
                prepared.preparation_cache_key, len(context.semantic_scene), len(context.active_characters),
            )
        else:
            # Legacy/miss path: read an already prepared semantic map only.
            # No image is available here, so this cannot invoke perception or
            # semantic graph construction.
            expansion = self._expansion.retrieve_or_expand(KnowledgeExpansionRequest(
                movie_id=request.movie_id, scene_id=request.scene_id, timestamp_seconds=request.timestamp_seconds,
            ), None)
            scene_id = expansion.scene_summary.scene_id if expansion.scene_summary else (request.scene_id or f"t{int(request.timestamp_seconds)}")
            context = self._context_builder.build(
                knowledge=expansion.record.knowledge, scene_id=scene_id, timestamp_seconds=request.timestamp_seconds,
                accessibility_profile=request.accessibility_profile,
            )
            knowledge_revision = expansion.record.revision
            knowledge_source = expansion.source
            self._logger.info(
                "[TRACE][PREPARED_CONTEXT] loaded=no cache_hit=no semantic_claims=%d active_characters=%d reused=no rebuilt=context_only",
                len(context.semantic_scene), len(context.active_characters),
            )
        log_claims("PreparedSceneContext.respond", context.semantic_scene, movie_id=request.movie_id, scene_id=context.scene_id)
        # Responding reads prepared knowledge and persistent memory only. It
        # must never turn a question click into another observation.
        timeline_state = self._timeline_memory.at(request.movie_id, request.timestamp_seconds)
        # A timestamp outside prepared semantic coverage returns a valid empty
        # state rather than leaking a later scene through a seek response.
        story_state = timeline_state.story_state if timeline_state is not None else StoryState(movie_id=request.movie_id, current_timestamp=request.timestamp_seconds)
        presentation = self._accessibility.reason(AccessibilityReasoningRequest(
            story_state=story_state,
            timeline_state=timeline_state,
            accessibility_profile=request.accessibility_profile,
            companion_profile=request.companion_profile,
        ))
        self._story_state.record_prompts(request.movie_id, context.timestamp_seconds, [prompt.id.removeprefix("prompt:") for prompt in presentation.prompt_bubbles if prompt.id.startswith("prompt:")])
        self._logger.info("[PROMPT] generated=%d", len(presentation.prompt_bubbles))
        self._logger.info("[PROMPT GENERATION] timestamp=%.2f generated=%d", context.timestamp_seconds, len(presentation.prompt_bubbles))
        self._logger.info("[VISUAL DRAWER] scene=%s story_events=%d unresolved_threads=%d", context.scene_id, len(presentation.live_story.recent_events) if presentation.live_story else 0, len(presentation.live_story.unresolved_story_threads) if presentation.live_story else 0)
        self._log_timeline_resolution(request.movie_id, request.timestamp_seconds, timeline_state, presentation)
        cache_key = self._cache_key(request, self._semantic_cache_version, scene_id, self._timestamp_bucket_seconds)
        response, cache_hit = self._response_cache.get_or_create(cache_key, lambda: GPTPersonalizationResponse(
            response=self._answer_from_scene(request.question, presentation), model="semantic-retrieval",
        ))
        return CompanionPipelineResponse(
            knowledge_source=knowledge_source, response_cache_hit=cache_hit, cache_key=cache_key,
            knowledge_revision=knowledge_revision, response=response, presentation=presentation,
        )

    def empty_response(self, request: CompanionPipelineRequest, reason: str) -> CompanionPipelineResponse:
        """Graceful semantic-cache failure: preserve the public JSON contract."""
        state = StoryState(movie_id=request.movie_id, current_timestamp=request.timestamp_seconds)
        presentation = self._accessibility.reason(AccessibilityReasoningRequest(
            story_state=state, accessibility_profile=request.accessibility_profile,
            companion_profile=request.companion_profile,
        ))
        self._logger.warning("[TIMELINE RESOLUTION] movie=%s timestamp=%.2f resolved=empty reason=%s", request.movie_id, request.timestamp_seconds, reason)
        return CompanionPipelineResponse(
            knowledge_source="retrieved", response_cache_hit=False,
            cache_key=f"{request.movie_id}:empty:{int(request.timestamp_seconds)}", knowledge_revision=1,
            response=GPTPersonalizationResponse(response="No verified semantic context is available for this timestamp yet.", model="semantic-retrieval"),
            presentation=presentation,
        )

    def empty_preparation(self, request: ScenePreparationRequest, reason: str) -> ScenePreparationResponse:
        state = StoryState(movie_id=request.movie_id, current_timestamp=request.timestamp_seconds)
        presentation = self._accessibility.reason(AccessibilityReasoningRequest(
            story_state=state, accessibility_profile=request.accessibility_profile,
            companion_profile=request.companion_profile,
        ))
        self._logger.warning("[TIMELINE RESOLUTION] movie=%s timestamp=%.2f resolved=empty reason=%s", request.movie_id, request.timestamp_seconds, reason)
        return ScenePreparationResponse(
            knowledge_source="retrieved", knowledge_revision=1, presentation=presentation,
            cache=PreparationCacheMetadata(cache_key=f"{request.movie_id}:empty:{int(request.timestamp_seconds)}", knowledge_revision=1, knowledge_source="retrieved", semantic_map_cached=False, reasoning_cached=False),
        )

    @staticmethod
    def _answer_from_scene(question: str, presentation) -> str:
        """Interaction answers are selected from the reasoner's semantic presentation only."""
        cards = presentation.character_cards
        if "who" in question.lower() and cards:
            return f"This is {cards[0].name}. {cards[0].reminder}"
        return presentation.scene_explanation

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

    def _log_timeline_resolution(self, movie_id, timestamp, timeline_state, presentation) -> None:
        memory = self._timeline_memory.get(movie_id)
        drawer = presentation.live_story
        self._logger.info(
            "[TIMELINE RESOLUTION] movie=%s timestamp=%.2f resolved=%s revision=%d prompts=%d characters=%d events=%d relationships=%d drawer=%s",
            movie_id, timestamp, timeline_state.timestamp if timeline_state else None, len(memory.intervals),
            len(presentation.prompt_bubbles), len(drawer.current_characters) if drawer else 0,
            len(drawer.recent_events) if drawer else 0, len(drawer.current_relationships) if drawer else 0,
            bool(drawer),
        )
