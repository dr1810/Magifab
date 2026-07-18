"""FastAPI application factory for the model-free backend foundation."""
import logging
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import Settings, get_settings
from services.object_detection import ObjectDetectionService
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


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the HTTP application without loading YOLO or Florence weights."""
    active_settings = settings or get_settings()
    configure_logging(active_settings)
    application = FastAPI(
        title=active_settings.app_name,
        version=active_settings.api_version,
        description="Modular MagiFab perception backend. Phase 3 provides detection and scene understanding only.",
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
    from routers.understand import router as understand_router
    application.include_router(health_router)
    application.include_router(detect_router)
    application.include_router(understand_router)
    return application


app = create_app()
