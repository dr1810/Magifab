"""Preparation-first runtime composition; interaction only reads prepared semantic knowledge."""
import hashlib
import json

from PIL import Image

from config import Settings
from schemas.accessibility_reasoning import AccessibilityReasoningRequest, CurrentScene
from schemas.companion_pipeline import CompanionPipelineRequest, CompanionPipelineResponse, ScenePreparationRequest, ScenePreparationResponse
from schemas.knowledge_expansion import KnowledgeExpansionRequest
from schemas.personalization import GPTPersonalizationResponse
from services.accessibility_reasoning import AccessibilityReasoningEngine
from services.knowledge_expansion import KnowledgeExpansionEngine
from services.response_cache import ResponseCache


class CompanionPipelineService:
    """Build scene knowledge during preparation; never invoke perception or GPT after a prompt click."""

    def __init__(self, expansion: KnowledgeExpansionEngine, accessibility: AccessibilityReasoningEngine, response_cache: ResponseCache, settings: Settings):
        self._expansion = expansion
        self._accessibility = accessibility
        self._response_cache = response_cache
        self._timestamp_bucket_seconds = settings.response_cache_timestamp_bucket_seconds

    def prepare(self, request: ScenePreparationRequest, image: Image.Image) -> ScenePreparationResponse:
        """Explore one representative unknown scene and persist all reusable observations."""
        expansion = self._expansion.retrieve_or_expand(KnowledgeExpansionRequest(
            movie_id=request.movie_id, scene_id=request.scene_id, timestamp_seconds=request.timestamp_seconds, preparation=True,
        ), image)
        current_scene = self._current_scene(expansion, request.scene_id, request.scene_summary)
        content = self._accessibility.reason(AccessibilityReasoningRequest(
            knowledge=expansion.record.knowledge, current_scene=current_scene, timestamp_seconds=request.timestamp_seconds,
            accessibility_profile=request.accessibility_profile, companion_profile=request.companion_profile,
        ))
        return ScenePreparationResponse(
            knowledge_source=expansion.source, knowledge_revision=expansion.record.revision,
            accessibility_content=content, perception=expansion.perception, semantic_matches=expansion.semantic_matches,
        )

    def respond(self, request: CompanionPipelineRequest) -> CompanionPipelineResponse:
        """Serve an instant answer from prepared facts; a miss is explicit and never triggers models."""
        expansion = self._expansion.retrieve_or_expand(KnowledgeExpansionRequest(
            movie_id=request.movie_id, scene_id=request.scene_id, timestamp_seconds=request.timestamp_seconds,
        ), None)
        scene_id = request.scene_id or (expansion.scene_summary.scene_id if expansion.scene_summary else f"t{int(request.timestamp_seconds)}")
        current_scene = self._current_scene(expansion, scene_id, request.scene_summary)
        content = self._accessibility.reason(AccessibilityReasoningRequest(
            knowledge=expansion.record.knowledge, current_scene=current_scene, timestamp_seconds=request.timestamp_seconds,
            accessibility_profile=request.accessibility_profile, companion_profile=request.companion_profile,
        ))
        cache_key = self._cache_key(request, expansion.record.revision, scene_id, self._timestamp_bucket_seconds)
        response, cache_hit = self._response_cache.get_or_create(cache_key, lambda: GPTPersonalizationResponse(
            response=self._answer_from_scene(request.question, expansion.scene_summary, content), model="semantic-retrieval",
        ))
        return CompanionPipelineResponse(
            knowledge_source="retrieved", response_cache_hit=cache_hit, cache_key=cache_key,
            knowledge_revision=expansion.record.revision, response=response, accessibility_content=content,
            perception=None, semantic_matches=None,
        )

    @staticmethod
    def _current_scene(expansion, fallback_scene_id: str, fallback_summary: str) -> CurrentScene:
        summary = expansion.scene_summary
        character_ids = [entity.semantic_id for entity in (summary.visible_entities if summary else []) if entity.semantic_id]
        return CurrentScene(scene_id=summary.scene_id if summary else fallback_scene_id, summary=summary.summary if summary else fallback_summary, character_ids=character_ids)

    @staticmethod
    def _answer_from_scene(question: str, summary, content) -> str:
        if not summary or not summary.prepared:
            return "No identifiable character or object is available for this scene."
        cards = content.drawer.character_cards
        visible = summary.visible_entities
        if "who" in question.lower() and cards:
            return f"This is {cards[0].name}. {cards[0].reminder}"
        if "who" in question.lower() and visible:
            return f"I can see a {visible[0].label}, but it is not confidently identified as a named character."
        return content.scene_summary or "This prepared scene has no additional explanation."

    @staticmethod
    def _cache_key(request: CompanionPipelineRequest, revision: int, scene_id: str, bucket_seconds: int) -> str:
        payload = {
            "movie_id": request.movie_id, "knowledge_revision": revision, "scene_id": scene_id,
            "timestamp_bucket": int(request.timestamp_seconds // bucket_seconds), "intent": request.intent.strip().lower(),
            "question": request.question.strip().lower(),
            "accessibility_profile": request.accessibility_profile.model_dump(mode="json"),
            "companion_profile": request.companion_profile.model_dump(mode="json"),
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
        return f"{request.movie_id}:v{revision}:{scene_id}:{digest}"
