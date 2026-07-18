"""End-to-end runtime composition of retrieval, perception, reasoning, and language personalization."""
import hashlib
import json

from PIL import Image

from schemas.accessibility_reasoning import AccessibilityReasoningRequest, CurrentScene
from schemas.companion_pipeline import CompanionPipelineRequest, CompanionPipelineResponse
from schemas.knowledge_expansion import KnowledgeExpansionRequest
from schemas.personalization import GPTPersonalizationRequest
from services.accessibility_reasoning import AccessibilityReasoningEngine
from services.gpt_personalization import GPTPersonalizationService
from services.knowledge_expansion import KnowledgeExpansionEngine
from config import Settings
from services.response_cache import ResponseCache


class CompanionPipelineService:
    """Coordinates existing services; all perception runs only for a knowledge-scene cache miss."""

    def __init__(self, expansion: KnowledgeExpansionEngine, accessibility: AccessibilityReasoningEngine, personalizer: GPTPersonalizationService, response_cache: ResponseCache, settings: Settings):
        self._expansion = expansion
        self._accessibility = accessibility
        self._personalizer = personalizer
        self._response_cache = response_cache
        self._timestamp_bucket_seconds = settings.response_cache_timestamp_bucket_seconds

    def respond(self, request: CompanionPipelineRequest, image: Image.Image | None) -> CompanionPipelineResponse:
        """Retrieve a scene first, expand only when needed, then cache personalized language by knowledge revision."""
        expansion_request = KnowledgeExpansionRequest(
            movie_id=request.movie_id,
            scene_id=request.scene_id,
            timestamp_seconds=request.timestamp_seconds,
            grounding_queries=request.grounding_queries,
            verify_faces=request.verify_faces,
        )
        expansion = self._expansion.retrieve_or_expand(expansion_request, image)
        scene_id = request.scene_id or (expansion.scene_summary.scene_id if expansion.scene_summary else f"t{int(request.timestamp_seconds)}")
        character_ids = [item.id for item in expansion.semantic_matches.characters] if expansion.semantic_matches else []
        current_scene = CurrentScene(scene_id=scene_id, summary=request.scene_summary, character_ids=character_ids)
        accessibility_content = self._accessibility.reason(AccessibilityReasoningRequest(
            knowledge=expansion.record.knowledge,
            current_scene=current_scene,
            timestamp_seconds=request.timestamp_seconds,
            accessibility_profile=request.accessibility_profile,
            companion_profile=request.companion_profile,
        ))
        cache_key = self._cache_key(request, expansion.record.revision, scene_id, self._timestamp_bucket_seconds)
        response, cache_hit = self._response_cache.get_or_create(cache_key, lambda: self._personalizer.personalize(
            GPTPersonalizationRequest(
                user_message=request.question,
                semantic_knowledge=expansion.record.knowledge,
                current_scene=current_scene,
                accessibility_content=accessibility_content,
                accessibility_profile=request.accessibility_profile,
                companion_profile=request.companion_profile,
            )
        ))
        return CompanionPipelineResponse(
            knowledge_source=expansion.source,
            response_cache_hit=cache_hit,
            cache_key=cache_key,
            knowledge_revision=expansion.record.revision,
            response=response,
            accessibility_content=accessibility_content,
            perception=expansion.perception,
            semantic_matches=expansion.semantic_matches,
        )

    def needs_perception(self, request: CompanionPipelineRequest) -> bool:
        """Expose the scene-level retrieval check so routers can avoid decoding a cached frame."""
        return self._expansion.needs_expansion(KnowledgeExpansionRequest(
            movie_id=request.movie_id,
            scene_id=request.scene_id,
            timestamp_seconds=request.timestamp_seconds,
            grounding_queries=request.grounding_queries,
            verify_faces=request.verify_faces,
        ))

    @staticmethod
    def _cache_key(request: CompanionPipelineRequest, revision: int, scene_id: str, bucket_seconds: int) -> str:
        """Revision and profile-aware keys make stale wording unreachable after knowledge updates."""
        payload = {
            "movie_id": request.movie_id,
            "knowledge_revision": revision,
            "scene_id": scene_id,
            "timestamp_bucket": int(request.timestamp_seconds // bucket_seconds),
            "intent": request.intent.strip().lower(),
            "question": request.question.strip().lower(),
            "grounding_queries": sorted(query.strip().lower() for query in request.grounding_queries),
            "verify_faces": request.verify_faces,
            "accessibility_profile": request.accessibility_profile.model_dump(mode="json"),
            "companion_profile": request.companion_profile.model_dump(mode="json"),
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
        return f"{request.movie_id}:v{revision}:{scene_id}:{digest}"
