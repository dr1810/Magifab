"""FastAPI application factory for the model-free backend foundation."""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import Settings, get_settings


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an application without loading models or coupling future phases to HTTP."""
    active_settings = settings or get_settings()
    configure_logging(active_settings)
    application = FastAPI(
        title=active_settings.app_name,
        version=active_settings.api_version,
        description="Model-free foundation for MagiFab's modular perception backend.",
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
    application.include_router(health_router)
    return application


app = create_app()
