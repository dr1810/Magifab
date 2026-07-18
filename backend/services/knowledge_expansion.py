"""Retrieval-first expansion engine; it turns current perception into factual movie knowledge."""
from hashlib import sha256
from uuid import uuid4

from PIL import Image

from models.knowledge_store import KnowledgeStore
from schemas.knowledge import (
    KnownAlias,
    KnowledgeRetrievalRequest,
    ObservationHistoryItem,
    SceneSummary,
    SemanticLocation,
    SemanticMovieKnowledge,
    SemanticObject,
    VisualAnchor,
    VisibleSceneEntity,
)
from schemas.knowledge_expansion import KnowledgeExpansionRequest, KnowledgeExpansionResult
from services.face_verification import FaceVerificationService
from services.knowledge_retriever import KnowledgeRetriever
from services.object_detection import ObjectDetectionService
from services.object_grounding import ObjectGroundingService
from services.perception_fusion import PerceptionFusionService
from services.semantic_matching import SemanticMatchingService
from services.vision_understanding import VisionUnderstandingService


class KnowledgeExpansionEngine:
    """Expands only a true knowledge miss; existing records always win over new perception."""

    def __init__(
        self,
        store: KnowledgeStore,
        retriever: KnowledgeRetriever,
        detector: ObjectDetectionService,
        vision: VisionUnderstandingService,
        fusion: PerceptionFusionService,
        matcher: SemanticMatchingService,
        grounder: ObjectGroundingService,
        face_verifier: FaceVerificationService,
    ):
        self._store = store
        self._retriever = retriever
        self._detector = detector
        self._vision = vision
        self._fusion = fusion
        self._matcher = matcher
        self._grounder = grounder
        self._face_verifier = face_verifier

    def retrieve_or_expand(self, request: KnowledgeExpansionRequest, image: Image.Image | None) -> KnowledgeExpansionResult:
        """Retrieve a known scene immediately; otherwise run only requested perception and persist observations."""
        retrieval = self._retriever.retrieve(KnowledgeRetrievalRequest(
            movie_id=request.movie_id,
            scene_id=request.scene_id,
            timestamp_seconds=request.timestamp_seconds,
        ))
        if retrieval.found and retrieval.record and retrieval.scene_summary and retrieval.scene_summary.prepared:
            return KnowledgeExpansionResult(
                source="retrieved",
                cache_key=_cache_key(request.movie_id, retrieval.record.revision, request.scene_id, request.timestamp_seconds),
                record=retrieval.record,
                scene_summary=retrieval.scene_summary,
            )
        if image is None:
            raise ValueError("image is required when movie knowledge or the requested scene is missing")

        detection = self._detector.detect(image)
        understanding = self._vision.understand(image)
        base_knowledge = retrieval.record.knowledge if retrieval.record else SemanticMovieKnowledge(movie_id=request.movie_id)
        grounding = self._grounder.locate(image, request.grounding_queries) if request.grounding_queries else None
        faces = self._face_verifier.verify(image, base_knowledge) if request.verify_faces and base_knowledge.face_references else None
        perception = self._fusion.fuse_current_outputs(detection, understanding, grounding, faces)
        semantic_matches = self._matcher.match(perception, base_knowledge)
        knowledge = self.merge_observations(base_knowledge, request, perception, semantic_matches)
        record = self._store.save(knowledge)
        scene_summary = next((scene for scene in knowledge.scene_summaries if scene.scene_id == (request.scene_id or "")), None)
        scene_summary = scene_summary or (knowledge.scene_summaries[-1] if knowledge.scene_summaries else None)
        return KnowledgeExpansionResult(
            source="expanded",
            cache_key=_cache_key(request.movie_id, record.revision, request.scene_id, request.timestamp_seconds),
            record=record,
            scene_summary=scene_summary,
            perception=perception,
            semantic_matches=semantic_matches,
        )

    def knowledge_exists(self, movie_id: str) -> bool:
        """Cheap cache check used to avoid decoding an image on an existing knowledge record."""
        return self._store.exists(movie_id)

    def needs_expansion(self, request: KnowledgeExpansionRequest) -> bool:
        """Avoid image decoding and model work when the requested scene is already represented."""
        retrieval = self._retriever.retrieve(KnowledgeRetrievalRequest(
            movie_id=request.movie_id,
            scene_id=request.scene_id,
            timestamp_seconds=request.timestamp_seconds,
        ))
        return not (retrieval.found and retrieval.scene_summary and retrieval.scene_summary.prepared)

    def merge_observations(
        self,
        base: SemanticMovieKnowledge,
        request: KnowledgeExpansionRequest,
        perception,
        semantic_matches,
    ) -> SemanticMovieKnowledge:
        """Persist scene-bound perception; only matcher-verified entities receive character IDs."""
        object_entities = [entity for entity in perception.entities if entity.category in {"object", "animal", "person"}]
        objects = [
            SemanticObject(
                id=_stable_id("object", entity.label),
                name=entity.label,
                perception_labels=[entity.label],
                aliases=[entity.label],
                confidence=entity.confidence or 0.0,
            )
            for entity in _unique_entities(object_entities)
        ]
        verified_character_ids = {match.entity.label.lower(): match.id for match in semantic_matches.characters}
        visible_entities = [
            VisibleSceneEntity(
                id=str(uuid4()), label=entity.label, category=entity.category,
                bbox=entity.bounding_box, confidence=entity.confidence or 0.0,
                sources=entity.sources, semantic_id=verified_character_ids.get(entity.label.lower()),
            )
            for entity in perception.entities
            if entity.category in {"person", "animal", "object"} and (entity.confidence or 0.0) > 0
        ]
        anchors = [
            VisualAnchor(
                id=str(uuid4()),
                semantic_id=verified_character_ids.get(entity.label.lower()) or _stable_id("object", entity.label),
                scene_id=request.scene_id,
                timestamp_seconds=request.timestamp_seconds,
                bbox=entity.bounding_box,
                confidence=entity.confidence or 0.0,
            )
            for entity in object_entities if entity.bounding_box is not None and entity.confidence is not None
        ]
        observations = [
            ObservationHistoryItem(
                id=str(uuid4()),
                timestamp_seconds=request.timestamp_seconds,
                entity_label=entity.label,
                semantic_id=_stable_id("object", entity.label),
                confidence=entity.confidence or 0.0,
                source=",".join(entity.sources),
            )
            for entity in object_entities
        ]
        aliases = [
            KnownAlias(semantic_id=_stable_id("object", entity.label), alias=entity.label, kind="observed_entity", confidence=entity.confidence or 0.0)
            for entity in _unique_entities(object_entities)
        ]
        locations = [SemanticLocation(id=_stable_id("location", perception.environment), name=perception.environment, aliases=[perception.environment])] if perception.environment else []
        scene_id = request.scene_id or _stable_id("scene", f"{request.movie_id}:{request.timestamp_seconds}")
        scene_confidence = _scene_confidence(object_entities)
        new_scene = SceneSummary(
                scene_id=scene_id,
                start_seconds=request.timestamp_seconds,
                end_seconds=request.timestamp_seconds,
                summary=perception.scene_description or "Observed movie frame.",
                confidence=scene_confidence,
                visible_entities=visible_entities,
                actions=perception.actions,
                interactions=perception.interactions,
                environment=perception.environment,
                potential_confusions=_potential_confusions(visible_entities, perception.actions),
                prepared=True,
            )
        return base.model_copy(update={
            "confidence": max(base.confidence, scene_confidence) if base.observation_history else scene_confidence,
            "objects": _merge_by_id(base.objects, objects),
            "locations": _merge_by_id(base.locations, locations),
            "scene_summaries": [scene for scene in base.scene_summaries if scene.scene_id != new_scene.scene_id] + [new_scene],
            "known_aliases": _merge_by_id(base.known_aliases, aliases, key="alias"),
            "visual_anchors": [*base.visual_anchors, *anchors],
            "observation_history": [*base.observation_history, *observations],
        })


def _cache_key(movie_id: str, revision: int, scene_id: str | None, timestamp_seconds: float) -> str:
    scene_key = scene_id or f"t{int(timestamp_seconds)}"
    return f"{movie_id}:v{revision}:{scene_key}"


def _stable_id(kind: str, label: str) -> str:
    return f"{kind}-{sha256(label.lower().encode('utf-8')).hexdigest()[:16]}"


def _unique_entities(entities):
    seen: set[str] = set()
    unique = []
    for entity in entities:
        key = entity.label.lower()
        if key not in seen:
            seen.add(key)
            unique.append(entity)
    return unique


def _scene_confidence(entities) -> float:
    confidences = [entity.confidence for entity in entities if entity.confidence is not None]
    return sum(confidences) / len(confidences) if confidences else 0.0


def _potential_confusions(entities, actions) -> list[str]:
    notes: list[str] = []
    if len([entity for entity in entities if entity.category in {"person", "animal"}]) > 1:
        notes.append("Several visible characters may be hard to tell apart.")
    if actions:
        notes.append("The visible action may need a simple explanation.")
    return notes


def _merge_by_id(existing, additions, key: str = "id"):
    seen = {getattr(item, key) for item in existing}
    return [*existing, *(item for item in additions if getattr(item, key) not in seen)]
