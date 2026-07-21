"""MagiFab's server-only movie preprocessing API."""
from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import Settings, get_settings
from services.movie_pipeline_retry import RetryExecutor
from services.movie_pipeline_service import MoviePipelineService
from services.movie_pipeline_storage import LocalMovieBlobStorage, SqliteMoviePipelineRepository
from services.video_chunk_service import FfmpegVideoChunker


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")


@lru_cache
def get_movie_blob_storage() -> LocalMovieBlobStorage:
    return LocalMovieBlobStorage(get_settings().movie_pipeline_dir)


@lru_cache
def get_movie_pipeline_repository() -> SqliteMoviePipelineRepository:
    return SqliteMoviePipelineRepository(get_settings().movie_pipeline_dir)


@lru_cache
def get_movie_pipeline_service() -> MoviePipelineService:
    """The only AI pipeline: Gemini video → Google Search → OpenAI scene reasoning."""
    from adapters.gemini_video_provider import GeminiVideoProvider
    from adapters.google_search_provider import GoogleSearchGroundingProvider
    from adapters.openai_scene_reasoner import OpenAISceneReasoner

    settings = get_settings()
    return MoviePipelineService(
        repository=get_movie_pipeline_repository(),
        blobs=get_movie_blob_storage(),
        chunker=FfmpegVideoChunker(get_movie_blob_storage()),
        visual_provider=GeminiVideoProvider(settings),
        search_provider=GoogleSearchGroundingProvider(settings),
        reasoning_provider=OpenAISceneReasoner(settings),
        chunk_duration_seconds=settings.movie_chunk_duration_seconds,
        retry_executor=RetryExecutor(settings.movie_pipeline_retry_attempts, settings.movie_pipeline_retry_base_seconds),
        model_versions={"gemini": settings.gemini_model, "openai": settings.openai_model, "scene_schema": "magifab-scene-v1"},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    configure_logging(active_settings)
    application = FastAPI(
        title=active_settings.app_name,
        version=active_settings.api_version,
        description="MagiFab offline movie preprocessing and stored-scene retrieval API.",
    )
    origins = [origin.strip() for origin in active_settings.cors_origins.split(",") if origin.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
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
    from routers.movies import router as movies_router

    application.include_router(health_router)
    application.include_router(movies_router)
    return application


app = create_app()
