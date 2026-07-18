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
)
from schemas.knowledge_expansion import KnowledgeExpansionRequest, KnowledgeExpansionResult
from services.knowledge_retriever import KnowledgeRetriever
from services.object_detection import ObjectDetectionService
from services.perception_fusion import PerceptionFusionService
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
    ):
        self._store = store
        self._retriever = retriever
        self._detector = detector
        self._vision = vision
        self._fusion = fusion

    def retrieve_or_expand(self, request: KnowledgeExpansionRequest, image: Image.Image | None) -> KnowledgeExpansionResult:
        """Retrieve immediately if present; otherwise run perception once and persist observed facts."""
        retrieval = self._retriever.retrieve(KnowledgeRetrievalRequest(
            movie_id=request.movie_id,
            scene_id=request.scene_id,
            timestamp_seconds=request.timestamp_seconds,
        ))
        if retrieval.found and retrieval.record:
            return KnowledgeExpansionResult(
                source="retrieved",
                cache_key=_cache_key(request.movie_id, retrieval.record.revision, request.scene_id, request.timestamp_seconds),
                record=retrieval.record,
                scene_summary=retrieval.scene_summary,
            )
        if image is None:
            raise ValueError("image is required when movie knowledge is missing")

        detection = self._detector.detect(image)
        understanding = self._vision.understand(image)
        perception = self._fusion.fuse_current_outputs(detection, understanding)
        knowledge = self._knowledge_from_perception(request, perception)
        record = self._store.save(knowledge)
        scene_summary = knowledge.scene_summaries[0] if knowledge.scene_summaries else None
        return KnowledgeExpansionResult(
            source="expanded",
            cache_key=_cache_key(request.movie_id, record.revision, request.scene_id, request.timestamp_seconds),
            record=record,
            scene_summary=scene_summary,
            perception=perception,
        )

    def knowledge_exists(self, movie_id: str) -> bool:
        """Cheap cache check used to avoid decoding an image on an existing knowledge record."""
        return self._store.exists(movie_id)

    def _knowledge_from_perception(self, request: KnowledgeExpansionRequest, perception) -> SemanticMovieKnowledge:
        """Create an empty graph then merge only the current observed facts into it."""
        return self.merge_observations(SemanticMovieKnowledge(movie_id=request.movie_id), request, perception)

    def merge_observations(
        self,
        base: SemanticMovieKnowledge,
        request: KnowledgeExpansionRequest,
        perception,
    ) -> SemanticMovieKnowledge:
        """Merge factual observations into any existing graph without naming characters or events."""
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
        anchors = [
            VisualAnchor(
                id=str(uuid4()),
                semantic_id=_stable_id("object", entity.label),
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
            )
        return base.model_copy(update={
            "confidence": max(base.confidence, scene_confidence) if base.observation_history else scene_confidence,
            "objects": _merge_by_id(base.objects, objects),
            "locations": _merge_by_id(base.locations, locations),
            "scene_summaries": _merge_by_id(base.scene_summaries, [new_scene], key="scene_id"),
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


def _merge_by_id(existing, additions, key: str = "id"):
    seen = {getattr(item, key) for item in existing}
    return [*existing, *(item for item in additions if getattr(item, key) not in seen)]
