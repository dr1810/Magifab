"""Preparation-first runtime composition; interaction only reads prepared semantic knowledge."""
import hashlib
import json
import logging
from time import perf_counter

from PIL import Image

from config import Settings
from schemas.accessibility_reasoning import AccessibilityReasoningRequest, CurrentScene
from schemas.companion_pipeline import (
    CompanionPipelineRequest,
    CompanionPipelineResponse,
    PreparationCacheMetadata,
    PreparedCharacter,
    PreparedObject,
    PreparedPromptBubble,
    PreparedSemanticGraph,
    ScenePreparationRequest,
    ScenePreparationResponse,
    SemanticGraphEdge,
    SemanticGraphNode,
)
from schemas.fusion import UnifiedEntity
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
        self._semantic_cache_version = settings.semantic_cache_version
        self._logger = logging.getLogger(__name__)

    def prepare(self, request: ScenePreparationRequest, image: Image.Image, frame_hash: str) -> ScenePreparationResponse:
        """Explore one representative unknown scene and persist all reusable observations."""
        started = perf_counter()
        expansion = self._expansion.retrieve_or_expand(KnowledgeExpansionRequest(
            movie_id=request.movie_id, scene_id=request.scene_id, timestamp_seconds=request.timestamp_seconds, frame_hash=frame_hash, preparation=True,
            grounding_queries=request.grounding_queries, verify_faces=request.verify_faces,
        ), image)
        current_scene = self._current_scene(expansion, request.scene_id, request.scene_summary)
        reasoning_started = perf_counter()
        content = self._accessibility.reason(AccessibilityReasoningRequest(
            knowledge=expansion.record.knowledge, current_scene=current_scene, timestamp_seconds=request.timestamp_seconds,
            accessibility_profile=request.accessibility_profile, companion_profile=request.companion_profile,
        ))
        self._logger.info("[TRACE][REASONING_ENGINE] executed=yes movie=%s scene=%s frame_hash=%s reasoning_rebuilt=yes output_prompts=%d drawer_cards=%d duration_ms=%.1f", request.movie_id, request.scene_id, frame_hash, len(content.prompt_bubbles), len(content.drawer.character_cards), (perf_counter() - reasoning_started) * 1000)
        grounded_entities = self._grounded_entities(expansion)
        characters = self._characters(expansion)
        objects = self._objects(expansion)
        prompt_bubbles = self._prompt_bubbles(content, expansion)
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
            accessibility_content=content, perception=expansion.perception, semantic_matches=expansion.semantic_matches,
            scene_summary=content.scene_summary,
            semantic_graph=semantic_graph,
            characters=characters,
            objects=objects,
            relationships=self._relationships(expansion),
            detected_objects=[entity for entity in grounded_entities if "object_detection" in entity.sources],
            grounded_entities=grounded_entities,
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
        current_scene = self._current_scene(expansion, scene_id, request.scene_summary)
        content = self._accessibility.reason(AccessibilityReasoningRequest(
            knowledge=expansion.record.knowledge, current_scene=current_scene, timestamp_seconds=request.timestamp_seconds,
            accessibility_profile=request.accessibility_profile, companion_profile=request.companion_profile,
        ))
        cache_key = self._cache_key(request, self._semantic_cache_version, scene_id, self._timestamp_bucket_seconds)
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
    def _grounded_entities(expansion) -> list[UnifiedEntity]:
        """Return the exact current-frame entities, including reconstructed cache hits."""
        if expansion.perception:
            return expansion.perception.entities
        summary = expansion.scene_summary
        if not summary:
            return []
        return [
            UnifiedEntity(
                label=entity.label,
                category=entity.category if entity.category in {"person", "animal", "object"} else "unknown",
                bounding_box=entity.bbox,
                confidence=entity.confidence,
                sources=entity.sources or ["semantic-cache"],
            )
            for entity in summary.visible_entities
        ]

    @staticmethod
    def _characters(expansion) -> list[PreparedCharacter]:
        summary = expansion.scene_summary
        visible_ids = {entity.semantic_id for entity in (summary.visible_entities if summary else []) if entity.semantic_id}
        anchors = {anchor.semantic_id: anchor for anchor in expansion.record.knowledge.visual_anchors if anchor.scene_id == (summary.scene_id if summary else None)}
        # Named entries come only from persisted knowledge / semantic matching;
        # raw detector labels are intentionally never promoted to identities.
        known = [character for character in expansion.record.knowledge.characters if not visible_ids or character.id in visible_ids]
        named = [
            PreparedCharacter(
                id=character.id,
                name=character.name,
                confidence=character.confidence,
                bounding_box=anchors.get(character.id).bbox if anchors.get(character.id) else None,
            )
            for character in known
        ]
        if named:
            return named
        # Surface visible animal/person targets without claiming a semantic
        # identity. This is an output projection only; matching remains intact.
        return [
            PreparedCharacter(
                id=entity.id,
                name=entity.label.replace("_", " ").title(),
                confidence=entity.confidence,
                bounding_box=entity.bbox,
                verified=False,
            )
            for entity in (summary.visible_entities if summary else [])
            if entity.category in {"person", "animal"}
        ]

    @staticmethod
    def _objects(expansion) -> list[PreparedObject]:
        summary = expansion.scene_summary
        visible = [entity for entity in (summary.visible_entities if summary else []) if entity.category == "object"]
        return [
            PreparedObject(
                id=entity.semantic_id or entity.id,
                name=entity.label,
                confidence=entity.confidence,
                bounding_box=entity.bbox,
                sources=entity.sources,
            )
            for entity in visible
        ]

    @staticmethod
    def _semantic_graph(expansion, fallback_scene_id: str) -> PreparedSemanticGraph:
        knowledge = expansion.record.knowledge
        summary = expansion.scene_summary
        nodes = [SemanticGraphNode(id=summary.scene_id if summary else fallback_scene_id, label=summary.summary if summary else fallback_scene_id, kind="scene", confidence=summary.confidence if summary else None)]
        nodes.extend(SemanticGraphNode(id=item.id, label=item.name, kind="character", confidence=item.confidence) for item in knowledge.characters)
        nodes.extend(SemanticGraphNode(id=item.id, label=item.name, kind="object", confidence=item.confidence) for item in knowledge.objects)
        nodes.extend(SemanticGraphNode(id=item.id, label=item.name, kind="location") for item in knowledge.locations)
        nodes.extend(SemanticGraphNode(id=item.id, label=item.description, kind="event") for item in knowledge.events)
        if summary:
            nodes.extend(
                SemanticGraphNode(
                    id=entity.semantic_id or entity.id,
                    label=entity.label,
                    kind=entity.category,
                    confidence=entity.confidence,
                )
                for entity in summary.visible_entities
                if entity.semantic_id is None
            )
        edges = [
            SemanticGraphEdge(from_id=item.from_character_id, to_id=item.to_character_id, kind="relationship", label=item.description)
            for item in knowledge.relationships
        ]
        if summary:
            edges.extend(
                SemanticGraphEdge(from_id=summary.scene_id, to_id=entity.semantic_id or entity.id, kind="visible_in")
                for entity in summary.visible_entities
            )
        return PreparedSemanticGraph(movie_id=knowledge.movie_id, scene_id=summary.scene_id if summary else fallback_scene_id, revision=expansion.record.revision, nodes=nodes, edges=edges)

    @staticmethod
    def _relationships(expansion) -> list[SemanticGraphEdge]:
        """Project Florence's current-frame interaction evidence without altering the semantic graph."""
        summary = expansion.scene_summary
        if not summary:
            return []
        entities = summary.visible_entities
        if not entities:
            return []
        source_id = entities[0].semantic_id or entities[0].id
        target_id = (entities[1].semantic_id or entities[1].id) if len(entities) > 1 else summary.scene_id
        return [
            SemanticGraphEdge(
                from_id=source_id,
                to_id=target_id,
                kind="observed_interaction",
                label=interaction,
            )
            for interaction in summary.interactions
        ]

    @staticmethod
    def _prompt_bubbles(content, expansion) -> list[PreparedPromptBubble]:
        visible = expansion.scene_summary.visible_entities if expansion.scene_summary else []
        cards = {card.name.lower(): card for card in content.drawer.character_cards}
        bubbles: list[PreparedPromptBubble] = []
        for prompt in content.prompt_bubbles:
            target = None
            bbox = None
            if prompt.kind in {"character", "visible_entity", "emotion"}:
                card = next(iter(cards.values()), None)
                target = card.name if card else next((entity.label for entity in visible if entity.category in {"person", "animal"}), None)
            elif prompt.kind == "object":
                entity = next((item for item in visible if item.category == "object"), None)
                target = entity.label if entity else None
                bbox = entity.bbox if entity else None
            if bbox is None and target:
                entity = next((item for item in visible if item.label.lower() == target.lower()), None)
                bbox = entity.bbox if entity else None
            bubbles.append(PreparedPromptBubble(
                id=prompt.id,
                type="who_is_that" if prompt.kind in {"character", "visible_entity"} else prompt.kind,
                title=prompt.label,
                question=prompt.question,
                text=(f"This is {target}." if target and prompt.kind in {"character", "visible_entity"} else prompt.label),
                target_entity=target, bounding_box=bbox, priority=prompt.priority,
            ))
        return bubbles

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
