"""FastAPI application factory for the model-free backend foundation."""
import logging
from functools import lru_cache

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import Settings, get_settings
from models.knowledge_store import KnowledgeStore
from services.knowledge_retriever import KnowledgeRetriever
from services.knowledge_expansion import KnowledgeExpansionEngine
from services.accessibility_reasoning import AccessibilityReasoningEngine
from services.face_verification import FaceVerificationService
from services.companion_pipeline import CompanionPipelineService
from services.object_grounding import ObjectGroundingService
from services.response_cache import ResponseCache
from services.gpt_personalization import GPTPersonalizationService
from services.knowledge_store import FileKnowledgeStore
from services.object_detection import ObjectDetectionService
from services.perception_fusion import PerceptionFusionService
from services.semantic_matching import SemanticMatchingService
from services.vision_understanding import VisionUnderstandingService
from services.model_manager import ModelManager
from services.observation_factory import ObservationFactory
from services.semantic_graph_builder import SemanticGraphBuilder
from services.movie_knowledge_provider import MovieKnowledgeProvider
from services.reasoning_context_builder import ReasoningContextBuilder
from services.companion_response_serializer import CompanionResponseSerializer
from services.prepared_scene_context_store import PreparedSceneContextStore
from services.sliding_window_memory import SlidingWindowMemoryManager
from services.story_event_extractor import StoryEventExtractor
from services.story_state_manager import StoryStateManager
from services.timeline_memory import TimelineMemoryService


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")


@lru_cache
def get_model_manager() -> ModelManager:
    """The sole owner of heavyweight perception adapters in this process."""
    return ModelManager(get_settings())


@lru_cache
def get_object_detection_service() -> ObjectDetectionService:
    return ObjectDetectionService(get_model_manager().yolo)


@lru_cache
def get_vision_understanding_service() -> VisionUnderstandingService:
    return VisionUnderstandingService(get_model_manager().florence)


@lru_cache
def get_perception_fusion_service() -> PerceptionFusionService:
    """Model-independent singleton; fusing supplied evidence never loads an AI model."""
    return PerceptionFusionService()


@lru_cache
def get_observation_factory() -> ObservationFactory:
    """Request-scoped observations are constructed here; the factory has no mutable scene state."""
    return ObservationFactory()


@lru_cache
def get_semantic_graph_builder() -> SemanticGraphBuilder:
    """Pure observation-to-claim transformer; it never exposes perception to the UI."""
    return SemanticGraphBuilder()


@lru_cache
def get_movie_knowledge_provider() -> MovieKnowledgeProvider:
    """Read-only supported-movie catalog cached once per process."""
    return MovieKnowledgeProvider()


@lru_cache
def get_reasoning_context_builder() -> ReasoningContextBuilder:
    """Retrieves only semantic claims for the accessibility reasoning boundary."""
    return ReasoningContextBuilder()


@lru_cache
def get_companion_response_serializer() -> CompanionResponseSerializer:
    """Presentation-only serializer with no perception or graph dependencies."""
    return CompanionResponseSerializer()


@lru_cache
def get_semantic_matching_service() -> SemanticMatchingService:
    """Pure structured matcher; it does not load a perception or language model."""
    return SemanticMatchingService(get_settings())


@lru_cache
def get_knowledge_store() -> KnowledgeStore:
    """Versioned file store for Phase 6; replace this dependency for a managed database."""
    settings = get_settings()
    return FileKnowledgeStore(settings.knowledge_store_dir, settings.semantic_cache_version)


@lru_cache
def get_knowledge_retriever() -> KnowledgeRetriever:
    """Retrieval-first boundary: a missing record does not trigger inference or GPT."""
    return KnowledgeRetriever(get_knowledge_store())


@lru_cache
def get_knowledge_expansion_engine() -> KnowledgeExpansionEngine:
    """Composes retrieval, perception, fusion, and persistence without any GPT dependency."""
    return KnowledgeExpansionEngine(
        store=get_knowledge_store(),
        retriever=get_knowledge_retriever(),
        detector=get_object_detection_service(),
        vision=get_vision_understanding_service(),
        fusion=get_perception_fusion_service(),
        matcher=get_semantic_matching_service(),
        grounder=get_object_grounding_service(),
        face_verifier=get_face_verification_service(),
        observation_factory=get_observation_factory(),
        graph_builder=get_semantic_graph_builder(),
        movie_knowledge_provider=get_movie_knowledge_provider(),
        cache_version=get_settings().semantic_cache_version,
    )


@lru_cache
def get_accessibility_reasoning_engine() -> AccessibilityReasoningEngine:
    """Pure deterministic reasoning engine; no model loading and no GPT dependency."""
    return AccessibilityReasoningEngine()


@lru_cache
def get_face_verification_service() -> FaceVerificationService:
    """Lazy face-perception dependency; it cannot access or assign movie character knowledge."""
    from adapters.retinaface_arcface_adapter import RetinaFaceArcFaceAdapter
    return FaceVerificationService(RetinaFaceArcFaceAdapter(get_settings()), get_settings())


@lru_cache
def get_object_grounding_service() -> ObjectGroundingService:
    return ObjectGroundingService(get_model_manager().grounding_dino)


@lru_cache
def get_response_cache() -> ResponseCache:
    """Process-local response cache; knowledge revision keys make stale entries unreachable."""
    return ResponseCache(get_settings())


@lru_cache
def get_prepared_scene_context_store() -> PreparedSceneContextStore:
    settings = get_settings()
    return PreparedSceneContextStore(settings.knowledge_store_dir, settings.semantic_cache_version)


@lru_cache
def get_sliding_window_memory_manager() -> SlidingWindowMemoryManager:
    """Process-local temporal state shared by preparation and response."""
    return SlidingWindowMemoryManager()


@lru_cache
def get_story_state_manager() -> StoryStateManager:
    """The only durable narrative memory owner in this backend process."""
    settings = get_settings()
    return StoryStateManager(settings.knowledge_store_dir, settings.semantic_cache_version)


@lru_cache
def get_story_event_extractor() -> StoryEventExtractor:
    return StoryEventExtractor()


@lru_cache
def get_timeline_memory_service() -> TimelineMemoryService:
    settings = get_settings()
    return TimelineMemoryService(settings.knowledge_store_dir, settings.semantic_cache_version)


@lru_cache
def get_companion_pipeline_service() -> CompanionPipelineService:
    """Full retrieval-first runtime composition; heavy providers stay lazy behind dependencies."""
    return CompanionPipelineService(
        expansion=get_knowledge_expansion_engine(),
        accessibility=get_accessibility_reasoning_engine(),
        response_cache=get_response_cache(),
        settings=get_settings(),
        context_builder=get_reasoning_context_builder(),
        serializer=get_companion_response_serializer(),
        prepared_contexts=get_prepared_scene_context_store(),
        memory=get_sliding_window_memory_manager(),
        story_state=get_story_state_manager(),
        story_events=get_story_event_extractor(),
        timeline_memory=get_timeline_memory_service(),
    )


@lru_cache
def get_gpt_personalization_service() -> GPTPersonalizationService:
    """Lazy server-only OpenAI integration; importing the app never initializes a client or exposes a key."""
    from adapters.openai_personalizer import OpenAIGPTPersonalizer
    return GPTPersonalizationService(OpenAIGPTPersonalizer(get_settings()))


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the HTTP application without loading YOLO or Florence weights."""
    active_settings = settings or get_settings()
    configure_logging(active_settings)
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Run once per worker before accepting requests. Model adapters themselves
        # remain import-safe and are never constructed by request handlers.
        await run_in_threadpool(get_model_manager().preload)
        yield

    application = FastAPI(
        title=active_settings.app_name,
        version=active_settings.api_version,
        description="Modular MagiFab backend with retrieval-first perception, semantic knowledge, accessibility reasoning, and GPT personalization.",
        lifespan=lifespan,
    )
    origins = [origin.strip() for origin in active_settings.cors_origins.split(",") if origin.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins or [],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @application.exception_handler(Exception)
    async def unhandled_exception(_: Request, error: Exception) -> JSONResponse:
        if isinstance(error, HTTPException):
            return JSONResponse(status_code=error.status_code, content={"detail": error.detail})
        logging.getLogger(__name__).exception("Unhandled request failure", exc_info=error)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    from routers.health import router as health_router
    from routers.detect import router as detect_router
    from routers.debug import router as debug_router
    from routers.fusion import router as fusion_router
    from routers.match import router as match_router
    from routers.knowledge import router as knowledge_router
    from routers.knowledge_expansion import router as knowledge_expansion_router
    from routers.accessibility_reasoning import router as accessibility_reasoning_router
    from routers.face_verification import router as face_verification_router
    from routers.grounding import router as grounding_router
    from routers.companion_pipeline import router as companion_pipeline_router
    from routers.personalization import router as personalization_router
    from routers.understand import router as understand_router
    application.include_router(health_router)
    application.include_router(detect_router)
    application.include_router(debug_router)
    application.include_router(fusion_router)
    application.include_router(match_router)
    application.include_router(knowledge_router)
    application.include_router(knowledge_expansion_router)
    application.include_router(accessibility_reasoning_router)
    application.include_router(face_verification_router)
    application.include_router(grounding_router)
    application.include_router(companion_pipeline_router)
    application.include_router(personalization_router)
    application.include_router(understand_router)
    return application


app = create_app()
