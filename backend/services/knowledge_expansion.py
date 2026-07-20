"""Retrieval-first expansion engine; it turns current perception into factual movie knowledge."""
from contextvars import ContextVar
from hashlib import sha256
import logging
from threading import RLock
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
from schemas.detection import DetectionResponse
from schemas.grounding import GroundingResponse
from schemas.understanding import UnderstandingResponse
from services.face_verification import FaceVerificationService
from services.knowledge_retriever import KnowledgeRetriever
from services.movie_knowledge_provider import MovieKnowledgeProvider
from services.object_detection import ObjectDetectionService
from services.object_grounding import ObjectGroundingService
from services.perception_fusion import PerceptionFusionService
from services.semantic_matching import SemanticMatchingService
from services.observation_factory import ObservationFactory
from services.semantic_graph_builder import SemanticGraphBuilder
from services.semantic_claim_audit import log_claims
from services.vision_understanding import VisionUnderstandingService

logger = logging.getLogger(__name__)

_GROUNDING_REUSE_CONFIDENCE = 0.82
_PROFILE_STAGES = (
    "movie_knowledge",
    "catalog_coverage",
    "knowledge_retrieval",
    "baseline_persistence",
    "semantic_planning",
    "yolo_detection",
    "grounding_dino",
    "florence_understanding",
    "face_verification",
    "perception_fusion",
    "semantic_matching",
    "observation_factory",
    "semantic_graph",
    "knowledge_merge",
    "knowledge_persistence",
)


class _IntervalProfiler:
    """Collect deterministic wall-clock timings for one preparation interval."""

    def __init__(self, movie_id: str, interval_id: str):
        self.movie_id = movie_id
        self.interval_id = interval_id
        self.started_at = perf_counter()
        self.stages: dict[str, float] = {}

    def record(self, stage: str, duration_seconds: float) -> None:
        self.stages[stage] = max(0.0, duration_seconds * 1000)

    def log(self, outcome: str) -> None:
        rows = [
            f"{stage:<28} {self.stages[stage]:9.1f} ms"
            if stage in self.stages else f"{stage:<28} {'skipped':>12}"
            for stage in _PROFILE_STAGES
        ]
        rows.append(f"{'total':<28} {(perf_counter() - self.started_at) * 1000:9.1f} ms")
        logger.info(
            "[INTERVAL_TIMING_TABLE] movie=%s interval=%s outcome=%s\n%s",
            self.movie_id,
            self.interval_id,
            outcome,
            "\n".join(rows),
        )


_active_interval_profiler: ContextVar[_IntervalProfiler | None] = ContextVar(
    "active_interval_profiler", default=None,
)


def _record_timing(stage: str, started_at: float) -> None:
    profiler = _active_interval_profiler.get()
    if profiler is not None:
        profiler.record(stage, perf_counter() - started_at)


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
        movie_knowledge_provider: MovieKnowledgeProvider | None = None,
        cache_version: int = 21,
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
        self._movie_knowledge_provider = movie_knowledge_provider or MovieKnowledgeProvider()
        self._cache_version = cache_version
        # Detector output is valid only for the exact captured frame. Grounding
        # is reused only for an unchanged entity plan that was fully confirmed
        # at high confidence; this avoids repeating the most expensive model
        # without turning partial evidence into a semantic fact.
        self._perception_cache_lock = RLock()
        self._detection_cache: dict[str, DetectionResponse] = {}
        self._grounding_cache: dict[str, GroundingResponse] = {}

    def retrieve_or_expand(self, request: KnowledgeExpansionRequest, image: Image.Image | None) -> KnowledgeExpansionResult:
        """Expand one interval and always emit a complete timing table."""
        profiler = _IntervalProfiler(request.movie_id, request.interval_id)
        token = _active_interval_profiler.set(profiler)
        outcome = "failed"
        try:
            result = self._retrieve_or_expand(request, image)
            outcome = result.source
            return result
        finally:
            profiler.log(outcome)
            _active_interval_profiler.reset(token)

    def _retrieve_or_expand(self, request: KnowledgeExpansionRequest, image: Image.Image | None) -> KnowledgeExpansionResult:
        """Retrieve a known scene immediately; otherwise run only requested perception and persist observations."""
        catalog_started = perf_counter()
        catalog = self._movie_knowledge_provider.get(request.movie_id)
        _record_timing("movie_knowledge", catalog_started)
        logger.info(
            "[TRACE][MOVIE_KNOWLEDGE] executed=yes movie=%s catalog_found=%s catalog_version=%s duration_ms=%.1f",
            request.movie_id, catalog is not None,
            catalog.movie_knowledge_version if catalog else None, (perf_counter() - catalog_started) * 1000,
        )
        if catalog is not None:
            logger.info(
                "[TRACE][KNOWLEDGE] movie=%s characters=%d relationships=%d events=%d timeline=%d emotions=%d scenes=%d",
                catalog.movie_id, len(catalog.characters), len(catalog.relationships), len(catalog.events),
                len(catalog.timeline_positions), len(catalog.emotions), len(catalog.movie_scenes),
            )
        coverage_started = perf_counter()
        covered, catalog_scene_id = self._movie_knowledge_provider.scene_coverage(catalog, request.catalog_scene_id, request.timestamp_seconds)
        _record_timing("catalog_coverage", coverage_started)
        logger.info(
            "[INTERVAL_CATALOG_COVERAGE] status=%s movie=%s requested_scene=%s timestamp=%.3f catalog_scene=%s",
            "PASS" if covered else "ANNOTATION_MISSING", request.movie_id, request.catalog_scene_id, request.timestamp_seconds, catalog_scene_id,
        )
        retrieval_started = perf_counter()
        retrieval = self._retriever.retrieve(KnowledgeRetrievalRequest(
            movie_id=request.movie_id,
            scene_id=request.interval_id,
            timestamp_seconds=request.timestamp_seconds,
        ))
        _record_timing("knowledge_retrieval", retrieval_started)
        cache_key = _cache_key(request.movie_id, self._cache_version, request.interval_id, request.timestamp_seconds, request.frame_hash)
        logger.info(
            "[TRACE][KNOWLEDGE_RETRIEVAL] executed=yes movie=%s scene=%s timestamp=%.3f frame_hash=%s cache_key=%s found=%s scene_prepared=%s duration_ms=%.1f",
            request.movie_id, request.interval_id, request.timestamp_seconds,
            request.frame_hash, cache_key, retrieval.found,
            bool(retrieval.scene_summary and retrieval.scene_summary.prepared), (perf_counter() - retrieval_started) * 1000,
        )
        if _cache_matches(retrieval, request, self._cache_version, catalog.movie_knowledge_version if catalog else None):
            logger.info("[TRACE][CACHE] semantic_map_replayed=yes movie=%s interval=%s frame_hash=%s key=%s", request.movie_id, request.interval_id, request.frame_hash, cache_key)
            return KnowledgeExpansionResult(
                source="retrieved",
                cache_key=cache_key,
                record=retrieval.record,
                scene_summary=retrieval.scene_summary,
            )
        # Persist the entire curated graph before a frame is interpreted. This
        # is the movie-level baseline: scene windows add observations to it but
        # can never make the story disappear when a detector misses a frame.
        if catalog is not None and retrieval.record is None:
            baseline_started = perf_counter()
            baseline = _runtime_knowledge(catalog, None, request.movie_id, self._cache_version)
            baseline_record = self._store.save(baseline)
            _record_timing("baseline_persistence", baseline_started)
            logger.info(
                "[TRACE][KNOWLEDGE_PERSISTENCE] baseline_saved=yes key=%s revision=%d characters=%d relationships=%d events=%d timeline=%d",
                _movie_knowledge_key(request.movie_id, self._cache_version), baseline_record.revision,
                len(baseline.characters), len(baseline.relationships), len(baseline.events), len(baseline.timeline_positions),
            )
        if image is None:
            raise ValueError("image is required when movie knowledge or the requested scene is missing")

        logger.info("[TRACE][CACHE] semantic_map_replayed=no movie=%s interval=%s frame_hash=%s key=%s perception_rebuilt=yes semantic_rebuilt=yes retrieval_rebuilt=yes", request.movie_id, request.interval_id, request.frame_hash, cache_key)
        # Movie knowledge is the perception plan.  Establish it before any
        # image model runs so a generic detector/caption can never decide what
        # this frame is "about".
        planning_started = perf_counter()
        base_knowledge = _runtime_knowledge(catalog, retrieval.record.knowledge if retrieval.record else None, request.movie_id, self._cache_version)
        expected = _expected_scene_entities(base_knowledge, request.catalog_scene_id, request.timestamp_seconds)
        catalog_window = next((item for item in base_knowledge.movie_scenes if item.scene_id == expected["scene_id"]), None)
        logger.info(
            "[TRACE][KNOWLEDGE_WINDOW] movie=%s knowledge_key=%s scene=%s start=%s end=%s overlap_seconds=%d",
            request.movie_id, _movie_knowledge_key(request.movie_id, self._cache_version), expected["scene_id"],
            catalog_window.start_seconds if catalog_window else None, catalog_window.end_seconds if catalog_window else None, 5,
        )
        grounding_queries = _grounding_queries(request.grounding_queries, expected, base_knowledge)
        _record_timing("semantic_planning", planning_started)
        logger.info(
            "[TRACE][EXPECTED_ENTITIES] movie=%s scene=%s characters=%s objects=%s locations=%s events=%s",
            request.movie_id, expected["scene_id"], expected["characters"], expected["objects"], expected["locations"], expected["events"],
        )
        logger.info("[TRACE][GROUNDING_DINO_QUERIES] movie=%s scene=%s queries=%s", request.movie_id, expected["scene_id"], grounding_queries)

        yolo_started = perf_counter()
        detection_cache_key = _detection_cache_key(request)
        with self._perception_cache_lock:
            cached_detection = self._detection_cache.get(detection_cache_key) if detection_cache_key else None
        if cached_detection is not None:
            detection = cached_detection.model_copy(deep=True)
            yolo_cache_hit = True
        else:
            detection = self._detector.detect(image)
            yolo_cache_hit = False
            if detection_cache_key:
                with self._perception_cache_lock:
                    self._detection_cache[detection_cache_key] = detection.model_copy(deep=True)
        _record_timing("yolo_detection", yolo_started)
        logger.info(
            "[TRACE][YOLO] executed=%s cache_hit=%s input=%dx%d output_detections=%d duration_ms=%.1f",
            not yolo_cache_hit, yolo_cache_hit, image.width, image.height, len(detection.detections), (perf_counter() - yolo_started) * 1000,
        )
        grounding_started = perf_counter()
        grounding_cache_key = _grounding_cache_key(request.movie_id, grounding_queries)
        with self._perception_cache_lock:
            cached_grounding = self._grounding_cache.get(grounding_cache_key) if grounding_cache_key else None
        if cached_grounding is not None:
            grounding = cached_grounding.model_copy(deep=True)
            grounding_cache_hit = True
        else:
            grounding = self._grounder.locate(image, grounding_queries) if grounding_queries else None
            grounding_cache_hit = False
            if grounding is not None and grounding_cache_key and _grounding_is_complete(grounding, grounding_queries):
                with self._perception_cache_lock:
                    self._grounding_cache[grounding_cache_key] = grounding.model_copy(deep=True)
        _record_timing("grounding_dino", grounding_started)
        logger.info(
            "[TRACE][GROUNDING_DINO] executed=%s cache_hit=%s entity_plan_reused=%s input_queries=%d output_matches=%d duration_ms=%.1f",
            bool(grounding_queries) and not grounding_cache_hit, grounding_cache_hit, grounding_cache_hit,
            len(grounding_queries), len(grounding.matches) if grounding else 0, (perf_counter() - grounding_started) * 1000,
        )
        logger.info("[TRACE][ENTITIES_CONFIRMED] movie=%s entities=%s", request.movie_id, [match.matched_object for match in grounding.matches] if grounding else [])
        logger.info("[TRACE][ENTITIES_REJECTED] movie=%s entities=%s", request.movie_id, [query for query in grounding_queries if not grounding or query.lower() not in {match.matched_object.lower() for match in grounding.matches}])
        # Florence runs after catalog-driven grounding.  Its output is retained
        # only as atmosphere/action enrichment; it is never identity evidence.
        florence_started = perf_counter()
        if _grounding_is_complete(grounding, grounding_queries):
            understanding = _grounded_understanding()
            florence_skipped = True
        else:
            understanding = self._vision.understand(image)
            florence_skipped = False
        _record_timing("florence_understanding", florence_started)
        accepted_enrichment, discarded_enrichment = _florence_enrichment(understanding)
        logger.info("[TRACE][FLORENCE_ENRICHMENT] accepted=%s discarded=%s", accepted_enrichment, discarded_enrichment)
        logger.info(
            "[TRACE][FLORENCE] executed=%s skipped_high_confidence_grounding=%s confidence_threshold=%.2f caption=%r output_objects=%s actions=%s interactions=%d duration_ms=%.1f",
            not florence_skipped, florence_skipped, _GROUNDING_REUSE_CONFIDENCE, understanding.scene_description, understanding.important_objects,
            understanding.detected_actions, len(understanding.interactions), (perf_counter() - florence_started) * 1000,
        )
        faces_started = perf_counter()
        faces = self._face_verifier.verify(image, base_knowledge) if request.verify_faces and base_knowledge.face_references else None
        _record_timing("face_verification", faces_started)
        fusion_started = perf_counter()
        perception = self._fusion.fuse_current_outputs(detection, understanding, grounding, faces)
        _record_timing("perception_fusion", fusion_started)
        logger.info("[TRACE][SEMANTIC_GRAPH_CONSTRUCTION] executed=yes fused_entities=%d duration_ms=%.1f", len(perception.entities), (perf_counter() - fusion_started) * 1000)
        # Matching returns semantic references, not claims. Claims first exist
        # only after SemanticGraphBuilder, so make that boundary explicit.
        log_claims("SemanticMatcher.input", base_knowledge.semantic_claims, movie_id=request.movie_id, scene_id=request.interval_id)
        matching_started = perf_counter()
        semantic_matches = self._matcher.match(
            perception, base_knowledge, scene_id=request.catalog_scene_id, timestamp_seconds=request.timestamp_seconds,
        )
        _record_timing("semantic_matching", matching_started)
        log_claims("SemanticMatcher.output", base_knowledge.semantic_claims, movie_id=request.movie_id, scene_id=request.interval_id)
        logger.info(
            "[TRACE][SEMANTIC_MATCHING] executed=yes catalog_queried=yes movie_scenes=%d scene_id=%s timestamp=%.3f "
            "input_entities=%d matched_characters=%d matched_locations=%d matched_objects=%d matched_events=%d matched_relationships=%d",
            len(base_knowledge.movie_scenes), request.interval_id, request.timestamp_seconds, len(perception.entities),
            len(semantic_matches.characters), len(semantic_matches.locations), len(semantic_matches.objects),
            len(semantic_matches.events), len(semantic_matches.relationships),
        )
        observation_started = perf_counter()
        observation = self._observation_factory.create(
            movie_id=request.movie_id,
            scene_id=request.interval_id,
            frame_hash=request.frame_hash or sha256(
                f"{request.movie_id}:{request.interval_id}:{request.timestamp_seconds}".encode("utf-8")
            ).hexdigest(),
            timestamp_seconds=request.timestamp_seconds,
            detection=detection,
            understanding=understanding,
            grounding=grounding,
        )
        _record_timing("observation_factory", observation_started)
        graph_started = perf_counter()
        claims = self._graph_builder.build(
            observation=observation,
            perception=perception,
            matches=semantic_matches,
            existing=base_knowledge,
            catalog_scene_id=expected["scene_id"],
        )
        _record_timing("semantic_graph", graph_started)
        log_claims("SemanticGraphBuilder.output", claims, movie_id=request.movie_id, scene_id=observation.scene_id)
        logger.info(
            "[TRACE][SEMANTIC_GRAPH_BUILDER] executed=yes observation_id=%s raw_caption_retained=observation_only claims=%d claim_kinds=%s",
            observation.id, len(claims), sorted({claim.kind for claim in claims}),
        )
        merge_started = perf_counter()
        knowledge = self.merge_observations(base_knowledge, request, perception, semantic_matches, observation, claims)
        _record_timing("knowledge_merge", merge_started)
        log_claims("KnowledgePersistence.input", knowledge.semantic_claims, movie_id=request.movie_id, scene_id=observation.scene_id)
        save_started = perf_counter()
        record = self._store.save(knowledge)
        _record_timing("knowledge_persistence", save_started)
        log_claims("KnowledgePersistence.output", record.knowledge.semantic_claims, movie_id=record.movie_id, scene_id=observation.scene_id)
        logger.info("[TRACE][KNOWLEDGE_PERSISTENCE] executed=yes revision=%d interval_visible_entities=%d duration_ms=%.1f", record.revision, len(next((scene.visible_entities for scene in knowledge.scene_summaries if scene.scene_id == request.interval_id), [])), (perf_counter() - save_started) * 1000)
        scene_summary = next((scene for scene in knowledge.scene_summaries if scene.scene_id == request.interval_id), None)
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

    def reset_movie(self, movie_id: str) -> None:
        """Discard stale semantic cache by key before interval zero is built."""
        self._store.discard_movie(movie_id)
        cache_prefix = f"{movie_id}:"
        with self._perception_cache_lock:
            self._detection_cache = {
                key: value for key, value in self._detection_cache.items()
                if not key.startswith(cache_prefix)
            }
            self._grounding_cache = {
                key: value for key, value in self._grounding_cache.items()
                if not key.startswith(cache_prefix)
            }
        logger.info("[SEMANTIC CACHE RESET] movie=%s schema_deserialization=no", movie_id)

    def needs_expansion(self, request: KnowledgeExpansionRequest) -> bool:
        """Avoid image decoding and model work when the requested interval is already represented."""
        retrieval = self._retriever.retrieve(KnowledgeRetrievalRequest(
            movie_id=request.movie_id,
            scene_id=request.interval_id,
            timestamp_seconds=request.timestamp_seconds,
        ))
        catalog = self._movie_knowledge_provider.get(request.movie_id)
        return not _cache_matches(retrieval, request, self._cache_version, catalog.movie_knowledge_version if catalog else None)

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
                scene_id=request.interval_id,
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
        scene_id = request.interval_id
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


def _cache_key(movie_id: str, cache_version: int, interval_id: str, timestamp_seconds: float, frame_hash: str | None) -> str:
    """Interval identity, never catalog-scene identity, owns runtime caching."""
    return f"{movie_id}:v{cache_version}:interval:{interval_id}"


def _detection_cache_key(request: KnowledgeExpansionRequest) -> str | None:
    """Cache YOLO only for an identical, caller-provided captured frame."""
    if not request.frame_hash:
        return None
    return f"{request.movie_id}:detection:{request.frame_hash}"


def _grounding_cache_key(movie_id: str, queries: list[str]) -> str | None:
    """Stable entity-plan key; a reordered but unchanged entity set is equivalent."""
    if not queries:
        return None
    normalized = "\x1f".join(sorted({query.strip().casefold() for query in queries if query.strip()}))
    if not normalized:
        return None
    return f"{movie_id}:grounding:{sha256(normalized.encode('utf-8')).hexdigest()}"


def _grounding_is_complete(grounding: GroundingResponse | None, queries: list[str]) -> bool:
    """Require every planned entity to be grounded before reusing or skipping Florence."""
    if grounding is None or not queries:
        return False
    confirmed = {
        match.matched_object.strip().casefold()
        for match in grounding.matches
        if match.confidence >= _GROUNDING_REUSE_CONFIDENCE
    }
    return all(query.strip().casefold() in confirmed for query in queries if query.strip())


def _grounded_understanding() -> UnderstandingResponse:
    """Explicitly mark that complete grounding made optional caption enrichment unnecessary."""
    return UnderstandingResponse(
        scene_description="",
        detected_actions=[],
        environment="",
        important_objects=[],
        interactions=[],
        model="skipped_high_confidence_grounding",
    )


def _movie_knowledge_key(movie_id: str, cache_version: int) -> str:
    """Stable persistent key for the whole movie graph, independent of frames."""
    return f"{movie_id}:v{cache_version}:knowledge"


def _cache_matches(retrieval, request: KnowledgeExpansionRequest, cache_version: int, catalog_version: int | None = None) -> bool:
    """A preparation replay is valid only for the identical movie interval."""
    summary = retrieval.scene_summary
    if not (retrieval.found and retrieval.record and summary and summary.prepared):
        return False
    if retrieval.record.movie_id != request.movie_id or retrieval.record.knowledge.movie_id != request.movie_id:
        logger.error("[TRACE][ISOLATION] rejected movie mismatch requested=%s record=%s knowledge=%s", request.movie_id, retrieval.record.movie_id, retrieval.record.knowledge.movie_id)
        return False
    if summary.preparation_version < cache_version or retrieval.record.knowledge.cache_version != cache_version:
        return False
    if catalog_version is not None and retrieval.record.knowledge.movie_knowledge_version != catalog_version:
        return False
    # A frame validates initial perception but interval identity owns a
    # prepared graph; catalog annotations cannot coalesce distinct intervals.
    if request.frame_hash is None:
        return True
    return summary.scene_id == request.interval_id


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


def _expected_scene_entities(knowledge: SemanticMovieKnowledge, scene_id: str | None, timestamp_seconds: float) -> dict[str, object]:
    """Return the catalog entities expected at this exact scene/time.

    This is deliberately independent of YOLO and Florence: those models may
    confirm an expectation, but cannot expand the movie's cast for a frame.
    """
    scene = next((item for item in knowledge.movie_scenes if item.scene_id == scene_id), None)
    scene = scene or next((item for item in knowledge.movie_scenes if item.start_seconds <= timestamp_seconds <= item.end_seconds), None)
    timeline_active = any(item.start_seconds <= timestamp_seconds <= item.end_seconds for item in knowledge.timeline_positions)
    if scene is None and timeline_active:
        prior = [item for item in knowledge.movie_scenes if item.start_seconds <= timestamp_seconds]
        scene = max(prior, key=lambda item: item.start_seconds) if prior else None
    if scene is None and knowledge.movie_scenes:
        # Missing catalog coverage enriches an interval with the nearest
        # authored context; it never prevents vision/memory preprocessing.
        scene = min(
            knowledge.movie_scenes,
            key=lambda item: min(abs(timestamp_seconds - item.start_seconds), abs(timestamp_seconds - item.end_seconds)),
        )
    character_ids = set(scene.character_ids) if scene else set()
    object_ids = set(scene.object_ids) if scene else set()
    event_ids = set(scene.event_ids) if scene else set()
    return {
        "scene_id": scene.scene_id if scene else scene_id,
        "characters": [item.name for item in knowledge.characters if item.id in character_ids],
        "character_labels": [label for item in knowledge.characters if item.id in character_ids for label in item.perception_labels],
        "objects": [item.name for item in knowledge.objects if item.id in object_ids],
        "locations": [item.name for item in knowledge.locations],
        "events": [item.description for item in knowledge.events if item.id in event_ids],
        "event_terms": [term for item in knowledge.events if item.id in event_ids for term in item.evidence_terms],
        "catalog_available": scene is not None,
    }


def _grounding_queries(requested: list[str], expected: dict[str, object], knowledge: SemanticMovieKnowledge) -> list[str]:
    """Generate DINO phrases from expected scene entities, never YOLO labels.

    Unsupported movies retain caller-provided queries for compatibility.  For
    catalog movies, caller hints are supplemental only and generic detections
    are intentionally excluded.
    """
    catalog_labels = [
        *expected["characters"], *expected["character_labels"], *expected["objects"],
        *expected["locations"], *expected["event_terms"],
    ]
    candidates = [*catalog_labels, *requested] if expected["catalog_available"] else [*requested]
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


def _florence_enrichment(understanding) -> tuple[list[str], list[str]]:
    """Audit Florence output without allowing environmental captions into claims."""
    environmental = ("sky", "tree", "trees", "grass", "landscape", "blue sky", "green grass")
    values = [understanding.scene_description, understanding.environment, *understanding.detected_actions, *understanding.important_objects, *understanding.interactions]
    accepted = [value for value in values if value and not any(term in value.lower() for term in environmental)]
    discarded = [value for value in values if value and value not in accepted]
    return accepted, discarded


def _runtime_knowledge(
    catalog: SemanticMovieKnowledge | None,
    stored: SemanticMovieKnowledge | None,
    movie_id: str,
    cache_version: int,
) -> SemanticMovieKnowledge:
    """Overlay a catalog onto runtime-only state without losing observations.

    Catalog facts own names, aliases, relationships and timeline. Stored state
    owns frame observations, derived graph claims and scene summaries. This is
    the movie-isolation boundary: neither collection is ever read from another
    movie ID.
    """
    if catalog is None:
        return (stored or SemanticMovieKnowledge(movie_id=movie_id)).model_copy(update={"cache_version": cache_version})
    if catalog.movie_id != movie_id:
        raise ValueError(f"movie knowledge isolation failure: {catalog.movie_id!r} != {movie_id!r}")
    if stored is None:
        return catalog.model_copy(update={"cache_version": cache_version})
    if stored.movie_id != movie_id:
        raise ValueError(f"stored knowledge isolation failure: {stored.movie_id!r} != {movie_id!r}")
    return catalog.model_copy(update={
        "cache_version": cache_version,
        "objects": _merge_by_id(catalog.objects, stored.objects),
        "locations": _merge_by_id(catalog.locations, stored.locations),
        "known_aliases": _merge_by_id(catalog.known_aliases, stored.known_aliases, key="alias"),
        "scene_summaries": stored.scene_summaries,
        "visual_anchors": stored.visual_anchors,
        "observation_history": stored.observation_history,
        "observations": stored.observations,
        "semantic_claims": stored.semantic_claims,
    })


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
