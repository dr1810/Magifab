"""FastAPI application factory for the model-free backend foundation."""
import logging
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import Settings, get_settings
from models.knowledge_store import KnowledgeStore
from services.knowledge_retriever import KnowledgeRetriever
from services.knowledge_expansion import KnowledgeExpansionEngine
from services.accessibility_reasoning import AccessibilityReasoningEngine
from services.knowledge_store import FileKnowledgeStore
from services.object_detection import ObjectDetectionService
from services.perception_fusion import PerceptionFusionService
from services.semantic_matching import SemanticMatchingService
from services.vision_understanding import VisionUnderstandingService


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")


@lru_cache
def get_object_detection_service() -> ObjectDetectionService:
    """Singleton service; YOLO itself remains unloaded until the first detection request."""
    from adapters.yolo_adapter import YOLOAdapter
    return ObjectDetectionService(YOLOAdapter(get_settings()))


@lru_cache
def get_vision_understanding_service() -> VisionUnderstandingService:
    """Singleton service; Florence weights remain unloaded until first understanding request."""
    from adapters.florence_adapter import FlorenceAdapter
    return VisionUnderstandingService(FlorenceAdapter(get_settings()))


@lru_cache
def get_perception_fusion_service() -> PerceptionFusionService:
    """Model-independent singleton; fusing supplied evidence never loads an AI model."""
    return PerceptionFusionService()


@lru_cache
def get_semantic_matching_service() -> SemanticMatchingService:
    """Pure structured matcher; it does not load a perception or language model."""
    return SemanticMatchingService(get_settings())


@lru_cache
def get_knowledge_store() -> KnowledgeStore:
    """Versioned file store for Phase 6; replace this dependency for a managed database."""
    return FileKnowledgeStore(get_settings().knowledge_store_dir)


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
    )


@lru_cache
def get_accessibility_reasoning_engine() -> AccessibilityReasoningEngine:
    """Pure deterministic reasoning engine; no model loading and no GPT dependency."""
    return AccessibilityReasoningEngine()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the HTTP application without loading YOLO or Florence weights."""
    active_settings = settings or get_settings()
    configure_logging(active_settings)
    application = FastAPI(
        title=active_settings.app_name,
        version=active_settings.api_version,
        description="Modular MagiFab backend. Phase 8 adds deterministic accessibility reasoning without GPT.",
    )
    origins = [origin.strip() for origin in active_settings.cors_origins.split(",") if origin.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins or [],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
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
    from routers.fusion import router as fusion_router
    from routers.match import router as match_router
    from routers.knowledge import router as knowledge_router
    from routers.knowledge_expansion import router as knowledge_expansion_router
    from routers.accessibility_reasoning import router as accessibility_reasoning_router
    from routers.understand import router as understand_router
    application.include_router(health_router)
    application.include_router(detect_router)
    application.include_router(fusion_router)
    application.include_router(match_router)
    application.include_router(knowledge_router)
    application.include_router(knowledge_expansion_router)
    application.include_router(accessibility_reasoning_router)
    application.include_router(understand_router)
    return application


app = create_app()
