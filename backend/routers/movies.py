"""Server-only movie upload and preprocessing APIs consumed by the companion."""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app import get_movie_pipeline_service
from config import Settings, get_settings
from schemas.movie_pipeline import ChunkRecord, MoviePreprocessResponse, MovieProcessingStatusResponse, MovieRecord, MovieUploadResponse, SceneLookupResponse, SceneRecord
from services.movie_pipeline_service import MoviePipelineService


router = APIRouter(prefix="/api/v1/movies", tags=["movie preprocessing"])


@router.post("/upload", response_model=MovieUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_movie(
    video: UploadFile = File(...),
    title: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
    service: MoviePipelineService = Depends(get_movie_pipeline_service),
) -> MovieUploadResponse:
    """Store a movie once; identical content returns its existing permanent record."""
    if not (video.content_type or "").startswith("video/"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="A video upload is required.")
    temporary = settings.movie_pipeline_dir / "uploads" / f"{uuid4()}.upload"
    temporary.parent.mkdir(parents=True, exist_ok=True)
    try:
        with temporary.open("wb") as output:
            while block := await video.read(1024 * 1024):
                output.write(block)
        if temporary.stat().st_size == 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The uploaded video is empty.")
        return service.upload(temporary, video.filename or "movie", video.content_type or "video/mp4", title)
    finally:
        await video.close()
        temporary.unlink(missing_ok=True)


@router.post("/{movie_id}/preprocess", response_model=MoviePreprocessResponse, status_code=status.HTTP_202_ACCEPTED)
def start_preprocessing(movie_id: str, background_tasks: BackgroundTasks, service: MoviePipelineService = Depends(get_movie_pipeline_service)) -> MoviePreprocessResponse:
    """Queue preprocessing. The browser never receives provider credentials or raw provider calls."""
    try:
        result = service.start(movie_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie was not found.") from error
    if result.accepted:
        background_tasks.add_task(service.preprocess, movie_id)
    return result


@router.get("/{movie_id}/processing-status", response_model=MovieProcessingStatusResponse)
def preprocessing_status(movie_id: str, service: MoviePipelineService = Depends(get_movie_pipeline_service)) -> MovieProcessingStatusResponse:
    try:
        return service.status(movie_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie was not found.") from error


@router.get("/{movie_id}", response_model=MovieRecord)
def movie_metadata(movie_id: str, service: MoviePipelineService = Depends(get_movie_pipeline_service)) -> MovieRecord:
    try:
        return service.movie(movie_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie was not found.") from error


@router.get("/{movie_id}/scene", response_model=SceneLookupResponse)
def active_scene(movie_id: str, timestamp: float = Query(ge=0), service: MoviePipelineService = Depends(get_movie_pipeline_service)) -> SceneLookupResponse:
    """Read the persisted scene for a playback timestamp; this endpoint has no AI side effects."""
    try:
        return service.scene_at(movie_id, timestamp)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie was not found.") from error


@router.get("/{movie_id}/video")
def stream_movie(movie_id: str, service: MoviePipelineService = Depends(get_movie_pipeline_service)) -> FileResponse:
    """Development source-video delivery. Production storage should issue an authorised signed URL."""
    try:
        movie = service.movie(movie_id)
        return FileResponse(service.source_path(movie_id), media_type=movie.mime_type, filename=movie.original_filename)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie was not found.") from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie source is unavailable.") from error


@router.get("/{movie_id}/scenes", response_model=list[SceneRecord])
def processed_scenes(movie_id: str, service: MoviePipelineService = Depends(get_movie_pipeline_service)) -> list[SceneRecord]:
    try:
        return service.scenes(movie_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie was not found.") from error


@router.get("/{movie_id}/chunks", response_model=list[ChunkRecord])
def chunk_data(movie_id: str, service: MoviePipelineService = Depends(get_movie_pipeline_service)) -> list[ChunkRecord]:
    try:
        return service.chunks(movie_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie was not found.") from error
