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
from services.accessibility_reasoning import AccessibilityReasoningEngine
from services.knowledge_expansion import KnowledgeExpansionEngine
from services.response_cache import ResponseCache
from services.reasoning_context_builder import ReasoningContextBuilder
from services.companion_response_serializer import CompanionResponseSerializer


class CompanionPipelineService:
    """Build scene knowledge during preparation; never invoke perception or GPT after a prompt click."""

    def __init__(self, expansion: KnowledgeExpansionEngine, accessibility: AccessibilityReasoningEngine, response_cache: ResponseCache, settings: Settings, context_builder: ReasoningContextBuilder | None = None, serializer: CompanionResponseSerializer | None = None):
        self._expansion = expansion
        self._accessibility = accessibility
        self._response_cache = response_cache
        self._timestamp_bucket_seconds = settings.response_cache_timestamp_bucket_seconds
        self._semantic_cache_version = settings.semantic_cache_version
        self._logger = logging.getLogger(__name__)
        self._context_builder = context_builder or ReasoningContextBuilder()
        self._serializer = serializer or CompanionResponseSerializer()

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
        presentation = self._accessibility.reason(AccessibilityReasoningRequest(
            context=context,
            companion_profile=request.companion_profile,
        ))
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
        expansion = self._expansion.retrieve_or_expand(KnowledgeExpansionRequest(
            movie_id=request.movie_id, scene_id=request.scene_id, timestamp_seconds=request.timestamp_seconds,
        ), None)
        # Retrieval may resolve a persisted prepared scene by timestamp even
        # when the caller supplies an alias/non-canonical scene ID. Context
        # must use that resolved scene ID or its claim filter becomes empty.
        scene_id = expansion.scene_summary.scene_id if expansion.scene_summary else (request.scene_id or f"t{int(request.timestamp_seconds)}")
        context = self._context_builder.build(
            knowledge=expansion.record.knowledge, scene_id=scene_id, timestamp_seconds=request.timestamp_seconds,
            accessibility_profile=request.accessibility_profile,
        )
        presentation = self._accessibility.reason(AccessibilityReasoningRequest(
            context=context,
            companion_profile=request.companion_profile,
        ))
        cache_key = self._cache_key(request, self._semantic_cache_version, scene_id, self._timestamp_bucket_seconds)
        response, cache_hit = self._response_cache.get_or_create(cache_key, lambda: GPTPersonalizationResponse(
            response=self._answer_from_scene(request.question, presentation), model="semantic-retrieval",
        ))
        return CompanionPipelineResponse(
            knowledge_source="retrieved", response_cache_hit=cache_hit, cache_key=cache_key,
            knowledge_revision=expansion.record.revision, response=response, presentation=presentation,
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
