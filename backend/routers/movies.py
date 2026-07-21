"""Server-only movie upload and preprocessing APIs consumed by the companion."""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app import get_movie_pipeline_service
from config import Settings, get_settings
from schemas.movie_pipeline import (
    CompanionChatResponse, MovieChatRequest, MoviePreprocessRequest, MoviePreprocessResponse,
    MovieProcessingStatusResponse, MovieUploadResponse, SceneArtifactResponse,
)
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
def start_preprocessing(movie_id: str, background_tasks: BackgroundTasks, request: MoviePreprocessRequest = MoviePreprocessRequest(), service: MoviePipelineService = Depends(get_movie_pipeline_service)) -> MoviePreprocessResponse:
    """Queue preprocessing. The browser never receives provider credentials or raw provider calls."""
    try:
        profile = request.companion_profile.model_dump(mode="json")
        result = service.start(movie_id, profile)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie was not found.") from error
    if result.accepted:
        background_tasks.add_task(service.preprocess, movie_id, profile)
    return result


@router.get("/{movie_id}/processing-status", response_model=MovieProcessingStatusResponse)
def preprocessing_status(movie_id: str, service: MoviePipelineService = Depends(get_movie_pipeline_service)) -> MovieProcessingStatusResponse:
    try:
        return service.status(movie_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie was not found.") from error


@router.get("/{movie_id}/scene", response_model=SceneArtifactResponse)
def active_scene(movie_id: str, timestamp: float = Query(ge=0), service: MoviePipelineService = Depends(get_movie_pipeline_service)) -> SceneArtifactResponse:
    """Read the persisted scene for a playback timestamp; this endpoint has no AI side effects."""
    try:
        lookup = service.scene_at(movie_id, timestamp)
        if not lookup.scene or not lookup.scene_window:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Movie artifacts are not ready.")
        return _artifact(lookup.scene.canonical_scene, lookup.scene_window.start_seconds)
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


@router.post("/{movie_id}/companion/chat", response_model=CompanionChatResponse)
def companion_chat(movie_id: str, request: MovieChatRequest, service: MoviePipelineService = Depends(get_movie_pipeline_service)) -> CompanionChatResponse:
    """Answer from stored scene artifacts. This endpoint never preprocesses or calls Gemini."""
    try:
        lookup = service.scene_at(movie_id, request.timestamp)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie was not found.") from error
    if not lookup.scene:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Movie artifacts are not ready.")
    scene = lookup.scene.canonical_scene
    answer = _stored_answer(scene.accessibility_explanation, scene, request.question)
    return CompanionChatResponse(answer=answer, timestamp=lookup.scene_window.start_seconds if lookup.scene_window else request.timestamp)


def _artifact(scene, timestamp: float) -> SceneArtifactResponse:
    prompts = [
        {"label": "What is happening?", "question": "What is happening?", "answer": scene.accessibility_explanation},
        *([{ "label": "Who is that?", "question": "Who is that?", "answer": scene.characters[0].description }] if scene.characters else []),
        *([{ "label": "Why does it matter?", "question": "Why does it matter?", "answer": scene.cause_effect[0].effect }] if scene.cause_effect else []),
        *([{ "label": "Remember this", "question": "What should I remember?", "answer": scene.important_memory[0] }] if scene.important_memory else []),
    ]
    return SceneArtifactResponse(
        timestamp=timestamp, promptBubble=prompts[:5], companionExplanation=scene.accessibility_explanation,
        visualDrawer={
            "characters": [{"name": item.name, "description": item.description, "emotion": ""} for item in scene.characters],
            "timeline": [*[item.event for item in scene.timeline], *scene.events],
            "objects": [{"name": item.name, "why": item.description} for item in scene.objects],
            "memory": scene.important_memory, "emotion": scene.emotions,
            "cause": [{"cause": item.cause, "effect": item.effect} for item in scene.cause_effect],
        }, visualAid=scene.visual_aid, characters=scene.characters, memoryCue=scene.important_memory,
    )


def _stored_answer(explanation: str, scene, question: str) -> str:
    """A no-model fallback keeps chat grounded when a deployment does not enable OpenAI chat."""
    lower = question.lower()
    if "who" in lower and scene.characters:
        return "; ".join(f"{item.name}: {item.description}" for item in scene.characters[:3])
    if "why" in lower and scene.cause_effect:
        item = scene.cause_effect[0]
        return f"{item.cause} This leads to: {item.effect}"
    if ("remember" in lower or "before" in lower) and scene.important_memory:
        return "Remember: " + " ".join(scene.important_memory[:2])
    return explanation
