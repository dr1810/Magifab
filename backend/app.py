"""MagiFab's server-only movie preprocessing API."""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import Settings, get_settings
from services.movie_pipeline_retry import RetryExecutor
from services.movie_pipeline_service import MoviePipelineService
from services.movie_pipeline_storage import LocalMovieBlobStorage, SqliteMoviePipelineRepository
from services.book_pipeline_service import BookPipelineService
from services.gemini_client import GeminiClient, GeminiClientConfigurationError, validate_gemini_sdk_import
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
    gemini_client = GeminiClient.from_settings(settings)
    return MoviePipelineService(
        repository=get_movie_pipeline_repository(),
        blobs=get_movie_blob_storage(),
        chunker=FfmpegVideoChunker(get_movie_blob_storage()),
        visual_provider=GeminiVideoProvider(settings, gemini_client=gemini_client),
        search_provider=GoogleSearchGroundingProvider(settings, gemini_client=gemini_client),
        reasoning_provider=OpenAISceneReasoner(settings),
        chunk_duration_seconds=settings.movie_chunk_duration_seconds,
        retry_executor=RetryExecutor(settings.movie_pipeline_retry_attempts, settings.movie_pipeline_retry_base_seconds),
        model_versions={"gemini": settings.gemini_model, "openai": settings.openai_model, "scene_schema": "magifab-scene-v1"},
        gemini_client=gemini_client,
    )


@lru_cache
def get_book_pipeline_service() -> BookPipelineService:
    from adapters.openai_book_reasoner import OpenAIBookReasoner
    settings = get_settings()
    service = BookPipelineService(settings.movie_pipeline_dir / "book-pipeline", OpenAIBookReasoner(settings))
    # The repository's first-class Dune asset is registered as a book, never as
    # a movie. Deployments can replace this with a catalog database entry.
    service.register_example(Path(__file__).resolve().parents[1] / "books" / "Frank Herbert - Dune 1 - Dune.pdf")
    return service


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    configure_logging(active_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        _validate_startup_dependencies(active_settings)
        yield

    application = FastAPI(
        title=active_settings.app_name,
        version=active_settings.api_version,
        description="MagiFab offline movie preprocessing and stored-scene retrieval API.",
        lifespan=lifespan,
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
    from routers.books import router as books_router

    application.include_router(health_router)
    application.include_router(movies_router)
    application.include_router(books_router)
    return application


def _validate_startup_dependencies(settings: Settings) -> None:
    logger = logging.getLogger(__name__)
    if not settings.gemini_api_key or not settings.gemini_api_key.get_secret_value().strip():
        raise RuntimeError("Backend startup validation failed: GEMINI_API_KEY is required but missing.")
    try:
        validate_gemini_sdk_import()
    except GeminiClientConfigurationError as error:
        raise RuntimeError(f"Backend startup validation failed: {error}") from error
    try:
        from openai import OpenAI
    except Exception as error:
        raise RuntimeError(
            "Backend startup validation failed: OpenAI SDK import failed. Install dependencies with `pip install -r backend/requirements.txt`."
        ) from error
    if OpenAI is None:
        raise RuntimeError("Backend startup validation failed: OpenAI SDK import returned no client type.")
    logger.info("Startup dependency validation succeeded for Gemini and OpenAI SDKs.")


app = create_app()
