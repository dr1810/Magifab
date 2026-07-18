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
    PreparedCharacter,
    PreparedPromptBubble,
    PreparedSemanticGraph,
    ScenePreparationRequest,
    ScenePreparationResponse,
    SemanticGraphEdge,
    SemanticGraphNode,
)
from schemas.knowledge_expansion import KnowledgeExpansionRequest
from schemas.personalization import GPTPersonalizationResponse
from services.accessibility_reasoning import AccessibilityReasoningEngine
from services.knowledge_expansion import KnowledgeExpansionEngine
from services.response_cache import ResponseCache
from services.reasoning_context_builder import ReasoningContextBuilder


class CompanionPipelineService:
    """Build scene knowledge during preparation; never invoke perception or GPT after a prompt click."""

    def __init__(self, expansion: KnowledgeExpansionEngine, accessibility: AccessibilityReasoningEngine, response_cache: ResponseCache, settings: Settings, context_builder: ReasoningContextBuilder | None = None):
        self._expansion = expansion
        self._accessibility = accessibility
        self._response_cache = response_cache
        self._timestamp_bucket_seconds = settings.response_cache_timestamp_bucket_seconds
        self._semantic_cache_version = settings.semantic_cache_version
        self._logger = logging.getLogger(__name__)
        self._context_builder = context_builder or ReasoningContextBuilder()

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
        content = self._accessibility.reason(AccessibilityReasoningRequest(
            context=context,
            companion_profile=request.companion_profile,
        ))
        self._logger.info("[TRACE][REASONING_ENGINE] executed=yes movie=%s scene=%s frame_hash=%s reasoning_rebuilt=yes output_prompts=%d drawer_cards=%d duration_ms=%.1f", request.movie_id, request.scene_id, frame_hash, len(content.prompt_bubbles), len(content.drawer.character_cards), (perf_counter() - reasoning_started) * 1000)
        prompt_bubbles = self._serialize_prompt_bubbles(content)
        semantic_graph = self._semantic_graph(expansion, request.scene_id)
        self._logger.info("[TRACE][SEMANTIC_GRAPH_RESPONSE] executed=yes nodes=%d edges=%d", len(semantic_graph.nodes), len(semantic_graph.edges))
        self._logger.info(
            "[TRACE][PROMPT_BUBBLE_PROJECTION] executed=yes input_prompts=%d input_list_id=%s input_first=%s output_prompts=%d output_list_id=%s output_first=%s",
            len(content.prompt_bubbles), id(content.prompt_bubbles), content.prompt_bubbles[0].label if content.prompt_bubbles else None,
            len(prompt_bubbles), id(prompt_bubbles), prompt_bubbles[0].title if prompt_bubbles else None,
        )
        self._logger.info("[TRACE][VISUAL_DRAWER] executed=yes cards=%d relationships=%d reminders=%d", len(content.drawer.character_cards), len(content.drawer.relationship_summaries), len(content.drawer.memory_reminders))
        response = ScenePreparationResponse(
            knowledge_source=expansion.source, knowledge_revision=expansion.record.revision,
            # Only graph-derived accessibility content crosses the normal
            # preparation boundary. Raw perception remains in observations.
            accessibility_content=content, perception=None, semantic_matches=None,
            scene_summary=content.scene_summary,
            semantic_graph=semantic_graph,
            characters=[
                PreparedCharacter(id=card.character_id, name=card.name, confidence=card.confidence, verified=True)
                for card in content.drawer.character_cards
            ],
            objects=[],
            relationships=[
                SemanticGraphEdge(from_id=item.relationship_id, to_id=item.relationship_id, kind="relationship", label=item.summary)
                for item in content.drawer.relationship_summaries
            ],
            detected_objects=[],
            grounded_entities=[],
            prompt_bubbles=prompt_bubbles,
            visual_drawer=content.drawer,
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
            len(response.prompt_bubbles), id(response.prompt_bubbles), response.prompt_bubbles[0].title if response.prompt_bubbles else None,
            len(response.accessibility_content.prompt_bubbles), id(response.accessibility_content.prompt_bubbles), response.accessibility_content.prompt_bubbles[0].label if response.accessibility_content.prompt_bubbles else None,
        )
        self._logger.info("[TRACE][PREPARE_SERVICE] complete source=%s duration_ms=%.1f", expansion.source, (perf_counter() - started) * 1000)
        return response

    def respond(self, request: CompanionPipelineRequest) -> CompanionPipelineResponse:
        """Serve an instant answer from prepared facts; a miss is explicit and never triggers models."""
        expansion = self._expansion.retrieve_or_expand(KnowledgeExpansionRequest(
            movie_id=request.movie_id, scene_id=request.scene_id, timestamp_seconds=request.timestamp_seconds,
        ), None)
        scene_id = request.scene_id or (expansion.scene_summary.scene_id if expansion.scene_summary else f"t{int(request.timestamp_seconds)}")
        context = self._context_builder.build(
            knowledge=expansion.record.knowledge, scene_id=scene_id, timestamp_seconds=request.timestamp_seconds,
            accessibility_profile=request.accessibility_profile,
        )
        content = self._accessibility.reason(AccessibilityReasoningRequest(
            context=context,
            companion_profile=request.companion_profile,
        ))
        cache_key = self._cache_key(request, self._semantic_cache_version, scene_id, self._timestamp_bucket_seconds)
        response, cache_hit = self._response_cache.get_or_create(cache_key, lambda: GPTPersonalizationResponse(
            response=self._answer_from_scene(request.question, content), model="semantic-retrieval",
        ))
        return CompanionPipelineResponse(
            knowledge_source="retrieved", response_cache_hit=cache_hit, cache_key=cache_key,
            knowledge_revision=expansion.record.revision, response=response, accessibility_content=content,
            perception=None, semantic_matches=None,
        )

    @staticmethod
    def _semantic_graph(expansion, fallback_scene_id: str) -> PreparedSemanticGraph:
        knowledge = expansion.record.knowledge
        summary = expansion.scene_summary
        scene_id = summary.scene_id if summary else fallback_scene_id
        claims = [claim for claim in knowledge.semantic_claims if claim.scene_id == scene_id]
        scene_state = next((claim for claim in claims if claim.kind == "scene_state"), None)
        nodes = [SemanticGraphNode(id=scene_id, label=scene_state.value if scene_state else scene_id, kind="scene", confidence=scene_state.confidence if scene_state else None)]
        nodes.extend(SemanticGraphNode(id=item.id, label=item.name, kind="character", confidence=item.confidence) for item in knowledge.characters)
        nodes.extend(SemanticGraphNode(id=item.id, label=item.name, kind="object", confidence=item.confidence) for item in knowledge.objects)
        nodes.extend(SemanticGraphNode(id=item.id, label=item.name, kind="location") for item in knowledge.locations)
        nodes.extend(SemanticGraphNode(id=item.id, label=item.description, kind="event") for item in knowledge.events)
        nodes.extend(
            SemanticGraphNode(id=claim.id, label=claim.value or claim.predicate, kind=claim.kind, confidence=claim.confidence)
            for claim in claims
            if claim.kind in {"event", "relationship", "timeline_change", "emotion", "callback"}
        )
        edges = [
            SemanticGraphEdge(from_id=item.from_character_id, to_id=item.to_character_id, kind="relationship", label=item.description)
            for item in knowledge.relationships
        ]
        edges.extend(
            SemanticGraphEdge(from_id=scene_id, to_id=claim.subject_id, kind=claim.predicate, label=claim.value)
            for claim in claims
            if claim.kind in {"character_present", "object_present", "timeline_change"}
        )
        return PreparedSemanticGraph(movie_id=knowledge.movie_id, scene_id=scene_id, revision=expansion.record.revision, nodes=nodes, edges=edges)

    @staticmethod
    def _serialize_prompt_bubbles(content) -> list[PreparedPromptBubble]:
        """A transparent DTO conversion; it does not inspect perception or graph objects."""
        return [
            PreparedPromptBubble(
                id=prompt.id,
                type="who_is_that" if prompt.kind == "character" else prompt.kind,
                title=prompt.label,
                question=prompt.question,
                text=prompt.label,
                priority=prompt.priority,
                claim_ids=prompt.claim_ids,
            )
            for prompt in content.prompt_bubbles
        ]

    @staticmethod
    def _answer_from_scene(question: str, content) -> str:
        """Interaction answers are selected from the reasoner's semantic presentation only."""
        cards = content.drawer.character_cards
        if "who" in question.lower() and cards:
            return f"This is {cards[0].name}. {cards[0].reminder}"
        return content.scene_summary

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
