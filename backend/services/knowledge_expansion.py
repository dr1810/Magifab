"""Retrieval-first expansion engine; it turns current perception into factual movie knowledge."""
from hashlib import sha256
import logging
from time import perf_counter
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
from services.observation_factory import ObservationFactory
from services.semantic_graph_builder import SemanticGraphBuilder
from services.vision_understanding import VisionUnderstandingService

logger = logging.getLogger(__name__)


class KnowledgeExpansionEngine:
    """Expands only a frame-identity cache miss; never reuses another frame's observations."""

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
        observation_factory: ObservationFactory | None = None,
        graph_builder: SemanticGraphBuilder | None = None,
        cache_version: int = 14,
    ):
        self._store = store
        self._retriever = retriever
        self._detector = detector
        self._vision = vision
        self._fusion = fusion
        self._matcher = matcher
        self._grounder = grounder
        self._face_verifier = face_verifier
        self._observation_factory = observation_factory or ObservationFactory()
        self._graph_builder = graph_builder or SemanticGraphBuilder()
        self._cache_version = cache_version

    def retrieve_or_expand(self, request: KnowledgeExpansionRequest, image: Image.Image | None) -> KnowledgeExpansionResult:
        """Retrieve a known scene immediately; otherwise run only requested perception and persist observations."""
        retrieval_started = perf_counter()
        retrieval = self._retriever.retrieve(KnowledgeRetrievalRequest(
            movie_id=request.movie_id,
            scene_id=request.scene_id,
            timestamp_seconds=request.timestamp_seconds,
        ))
        cache_key = _cache_key(request.movie_id, self._cache_version, request.scene_id, request.timestamp_seconds, request.frame_hash)
        logger.info(
            "[TRACE][KNOWLEDGE_RETRIEVAL] executed=yes movie=%s scene=%s timestamp=%.3f frame_hash=%s cache_key=%s found=%s scene_prepared=%s duration_ms=%.1f",
            request.movie_id, request.scene_id, request.timestamp_seconds,
            request.frame_hash, cache_key, retrieval.found,
            bool(retrieval.scene_summary and retrieval.scene_summary.prepared), (perf_counter() - retrieval_started) * 1000,
        )
        if _cache_matches(retrieval, request, self._cache_version):
            logger.info("[TRACE][CACHE] semantic_map_replayed=yes movie=%s scene=%s frame_hash=%s key=%s", request.movie_id, request.scene_id, request.frame_hash, cache_key)
            return KnowledgeExpansionResult(
                source="retrieved",
                cache_key=cache_key,
                record=retrieval.record,
                scene_summary=retrieval.scene_summary,
            )
        if image is None:
            raise ValueError("image is required when movie knowledge or the requested scene is missing")

        logger.info("[TRACE][CACHE] semantic_map_replayed=no movie=%s scene=%s frame_hash=%s key=%s perception_rebuilt=yes semantic_rebuilt=yes retrieval_rebuilt=yes", request.movie_id, request.scene_id, request.frame_hash, cache_key)
        yolo_started = perf_counter()
        detection = self._detector.detect(image)
        logger.info("[TRACE][YOLO] executed=yes input=%dx%d output_detections=%d duration_ms=%.1f", image.width, image.height, len(detection.detections), (perf_counter() - yolo_started) * 1000)
        florence_started = perf_counter()
        understanding = self._vision.understand(image)
        logger.info("[TRACE][FLORENCE] executed=yes caption=%r output_objects=%s actions=%s interactions=%d duration_ms=%.1f", understanding.scene_description, understanding.important_objects, understanding.detected_actions, len(understanding.interactions), (perf_counter() - florence_started) * 1000)
        base_knowledge = retrieval.record.knowledge if retrieval.record else SemanticMovieKnowledge(movie_id=request.movie_id)
        # Grounding is part of preparation, not an interaction-time fallback.
        # Use caller hints when available and otherwise ground labels observed by
        # YOLO in this exact frame. This keeps queries evidence-led and supports
        # arbitrary uploaded movies without hard-coded object names.
        grounding_queries = _grounding_queries(request.grounding_queries, detection.detections)
        grounding_started = perf_counter()
        grounding = self._grounder.locate(image, grounding_queries) if grounding_queries else None
        logger.info("[TRACE][GROUNDING_DINO] executed=%s input_queries=%d output_matches=%d duration_ms=%.1f", bool(grounding_queries), len(grounding_queries), len(grounding.matches) if grounding else 0, (perf_counter() - grounding_started) * 1000)
        faces = self._face_verifier.verify(image, base_knowledge) if request.verify_faces and base_knowledge.face_references else None
        fusion_started = perf_counter()
        perception = self._fusion.fuse_current_outputs(detection, understanding, grounding, faces)
        logger.info("[TRACE][SEMANTIC_GRAPH_CONSTRUCTION] executed=yes fused_entities=%d duration_ms=%.1f", len(perception.entities), (perf_counter() - fusion_started) * 1000)
        semantic_matches = self._matcher.match(perception, base_knowledge)
        logger.info("[TRACE][SEMANTIC_MATCHING] executed=yes input_entities=%d matched_characters=%d", len(perception.entities), len(semantic_matches.characters))
        observation = self._observation_factory.create(
            movie_id=request.movie_id,
            scene_id=request.scene_id or _stable_id("scene", f"{request.movie_id}:{request.timestamp_seconds}"),
            frame_hash=request.frame_hash or sha256(
                f"{request.movie_id}:{request.scene_id}:{request.timestamp_seconds}".encode("utf-8")
            ).hexdigest(),
            timestamp_seconds=request.timestamp_seconds,
            detection=detection,
            understanding=understanding,
            grounding=grounding,
        )
        claims = self._graph_builder.build(
            observation=observation, perception=perception, matches=semantic_matches, existing=base_knowledge,
        )
        logger.info(
            "[TRACE][SEMANTIC_GRAPH_BUILDER] executed=yes observation_id=%s raw_caption_retained=yes claims=%d claim_kinds=%s",
            observation.id, len(claims), sorted({claim.kind for claim in claims}),
        )
        knowledge = self.merge_observations(base_knowledge, request, perception, semantic_matches, observation, claims)
        save_started = perf_counter()
        record = self._store.save(knowledge)
        logger.info("[TRACE][KNOWLEDGE_PERSISTENCE] executed=yes revision=%d scene_visible_entities=%d duration_ms=%.1f", record.revision, len(next((scene.visible_entities for scene in knowledge.scene_summaries if scene.scene_id == request.scene_id), [])), (perf_counter() - save_started) * 1000)
        scene_summary = next((scene for scene in knowledge.scene_summaries if scene.scene_id == (request.scene_id or "")), None)
        scene_summary = scene_summary or (knowledge.scene_summaries[-1] if knowledge.scene_summaries else None)
        return KnowledgeExpansionResult(
            source="expanded",
            cache_key=cache_key,
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
        return not _cache_matches(retrieval, request, self._cache_version)

    def merge_observations(
        self,
        base: SemanticMovieKnowledge,
        request: KnowledgeExpansionRequest,
        perception,
        semantic_matches,
        observation,
        claims,
    ) -> SemanticMovieKnowledge:
        """Persist raw observations separately and integrate only graph claims as semantic facts."""
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
        # Florence object detections are text-only and intentionally have no
        # box confidence. Keep that evidence in the scene map with a neutral
        # confidence instead of silently dropping it before prompt generation.
        visible_entities = [
            VisibleSceneEntity(
                id=str(uuid4()), label=entity.label, category=entity.category,
                bbox=entity.bounding_box,
                confidence=entity.confidence if entity.confidence is not None else 0.5,
                sources=entity.sources, semantic_id=verified_character_ids.get(entity.label.lower()),
            )
            for entity in perception.entities
            if entity.category in {"person", "animal", "object"}
            and (entity.confidence is not None and entity.confidence > 0 or "scene_understanding" in entity.sources)
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
        # A Florence environment phrase is raw perception evidence. It remains
        # in the observation layer and is not promoted to a semantic location.
        locations: list[SemanticLocation] = []
        scene_id = request.scene_id or _stable_id("scene", f"{request.movie_id}:{request.timestamp_seconds}")
        scene_confidence = _scene_confidence(object_entities)
        semantic_scene_state = next((claim.value for claim in claims if claim.kind == "scene_state"), "")
        new_scene = SceneSummary(
                scene_id=scene_id,
                frame_hash=request.frame_hash,
                start_seconds=request.timestamp_seconds,
                end_seconds=request.timestamp_seconds,
                # Compatibility projection for existing APIs. This is derived
                # from graph claims, never Florence's raw caption.
                summary=semantic_scene_state or "Observed movie frame.",
                confidence=scene_confidence,
                visible_entities=visible_entities,
                actions=perception.actions,
                interactions=perception.interactions,
                environment=perception.environment,
                potential_confusions=_potential_confusions(visible_entities, perception.actions),
                prepared=True,
                preparation_version=self._cache_version,
            )
        return base.model_copy(update={
            "cache_version": self._cache_version,
            "confidence": max(base.confidence, scene_confidence) if base.observation_history else scene_confidence,
            "objects": _merge_by_id(base.objects, objects),
            "locations": _merge_by_id(base.locations, locations),
            "scene_summaries": [scene for scene in base.scene_summaries if scene.scene_id != new_scene.scene_id] + [new_scene],
            "known_aliases": _merge_by_id(base.known_aliases, aliases, key="alias"),
            "visual_anchors": [*base.visual_anchors, *anchors],
            "observation_history": [*base.observation_history, *observations],
            "observations": [item for item in base.observations if item.scene_id != scene_id] + [observation],
            "semantic_claims": [claim for claim in base.semantic_claims if claim.scene_id != scene_id] + claims,
        })


def _cache_key(movie_id: str, cache_version: int, scene_id: str | None, timestamp_seconds: float, frame_hash: str | None) -> str:
    scene_key = scene_id or f"t{int(timestamp_seconds)}"
    frame_key = frame_hash[:16] if frame_hash else "no-frame"
    return f"{movie_id}:v{cache_version}:{scene_key}:t{timestamp_seconds:.3f}:h{frame_key}"


def _cache_matches(retrieval, request: KnowledgeExpansionRequest, cache_version: int) -> bool:
    """A preparation replay is valid only for the identical movie, scene, time and frame."""
    summary = retrieval.scene_summary
    if not (retrieval.found and retrieval.record and summary and summary.prepared):
        return False
    if retrieval.record.movie_id != request.movie_id or retrieval.record.knowledge.movie_id != request.movie_id:
        logger.error("[TRACE][ISOLATION] rejected movie mismatch requested=%s record=%s knowledge=%s", request.movie_id, retrieval.record.movie_id, retrieval.record.knowledge.movie_id)
        return False
    if summary.preparation_version < cache_version or retrieval.record.knowledge.cache_version != cache_version:
        return False
    # /respond has no image. It can read a current scene record, but it never
    # runs perception or writes a cache. /prepare always provides a fingerprint
    # and must match all four identity components.
    if request.frame_hash is None:
        return True
    return (
        summary.scene_id == (request.scene_id or summary.scene_id)
        and abs(summary.start_seconds - request.timestamp_seconds) < 0.001
        and summary.frame_hash == request.frame_hash
    )


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


def _grounding_queries(requested: list[str], detections) -> list[str]:
    """Return unique, bounded phrases anchored in caller intent or YOLO output."""
    candidates = [*requested, *(detection.label for detection in detections)]
    queries: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        cleaned = value.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            queries.append(cleaned)
        if len(queries) == 20:
            break
    return queries


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
