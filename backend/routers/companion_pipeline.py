"""Retrieval-first runtime endpoint for the full MagiFab backend pipeline."""
import logging
from fastapi import APIRouter, Depends, HTTPException, status

from adapters.openai_personalizer import PersonalizationConfigurationError, PersonalizationProviderError
from app import get_book_scene_pipeline, get_companion_pipeline_service
from config import Settings, get_settings
from schemas.companion_pipeline import CompanionInterval, CompanionIntervalPreparationRequest, CompanionIntervalPromptRequest, CompanionPipelineRequest, CompanionPipelineResponse, IntervalPreparationRequest, IntervalPreparationResponse, PreprocessingCompletionRequest
from services.companion_pipeline import CompanionPipelineService
from services.book_scene_pipeline import BookScenePipeline
from services.frame_validation import InvalidFrameError, validate_frame
from utils.image import decode_base64_image_with_size

router = APIRouter(prefix="/api/v1/companion", tags=["companion pipeline"])
logger = logging.getLogger(__name__)


@router.post("/preprocessing/complete")
def complete_preprocessing(
    request: PreprocessingCompletionRequest,
    service: CompanionPipelineService = Depends(get_companion_pipeline_service),
) -> dict[str, int | str | bool]:
    """Validate the completed movie cache without returning presentation data."""
    try:
        return service.complete_preprocessing(request)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Movie interval preprocessing is incomplete.") from error


@router.post("/respond", response_model=CompanionPipelineResponse)
def respond(
    request: CompanionPipelineRequest,
    settings: Settings = Depends(get_settings),
    service: CompanionPipelineService = Depends(get_companion_pipeline_service),
) -> CompanionPipelineResponse:
    """Prompt interaction is retrieval-only: no image decoding, perception, or GPT work is allowed."""
    try:
        return service.respond(request)
    except (ValueError, AssertionError) as error:
        # A missing snapshot is a preprocessing failure, never a reason to
        # recreate StoryState or prompts while the user is watching.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This interval has not been preprocessed.") from error
    except PersonalizationConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GPT personalization is not configured") from error
    except PersonalizationProviderError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GPT personalization is unavailable") from error


@router.post("/intervals/respond", response_model=CompanionPipelineResponse)
def respond_to_companion_interval(
    request: CompanionIntervalPromptRequest,
    service: CompanionPipelineService = Depends(get_companion_pipeline_service),
) -> CompanionPipelineResponse:
    """Answer from a prepared interval without requiring a source-specific type."""
    normalized = CompanionPipelineRequest(
        movie_id=request.contentId,
        timestamp_seconds=request.timestamp,
        question=request.question,
        intent=request.intent,
        grounding_queries=request.grounding_queries,
        verify_faces=request.verify_faces,
        accessibility_profile=request.accessibility_profile,
        companion_profile=request.companion_profile,
    )
    try:
        return service.respond(normalized)
    except (ValueError, AssertionError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This content interval has not been preprocessed.") from error
    except PersonalizationConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GPT personalization is not configured") from error
    except PersonalizationProviderError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GPT personalization is unavailable") from error


@router.post("/intervals/prepare", response_model=IntervalPreparationResponse)
def prepare_companion_interval(
    request: CompanionIntervalPreparationRequest,
    settings: Settings = Depends(get_settings),
    service: CompanionPipelineService = Depends(get_companion_pipeline_service),
    book_pipeline: BookScenePipeline = Depends(get_book_scene_pipeline),
) -> IntervalPreparationResponse:
    """Prepare any provider's interval without branching on its source type."""
    interval = request.interval
    if interval.metadata.get("provider") == "book":
        return book_pipeline.prepare(interval)
    normalized = _normalize_companion_interval(interval, request.accessibility_profile, request.companion_profile)
    try:
        image, file_size, frame_hash = decode_base64_image_with_size(interval.image, settings)
        validate_frame(image, file_size=file_size, timestamp=interval.timestamp, debug_dir=settings.debug_frames_dir, movie_id=interval.contentId, scene_id=interval.id, frame_hash=frame_hash)
        logger.info("[COMPANION_INTERVAL_PREPARE] content=%s interval=%s start=%s end=%s text_chars=%d metadata=%s", interval.contentId, interval.id, interval.start, interval.end, len(interval.text), interval.metadata)
        return service.prepare(normalized, image, frame_hash)
    except InvalidFrameError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A valid rendered interval image is required.") from error
    except (ValueError, AssertionError) as error:
        logger.exception("[COMPANION_INTERVAL_FAILED] content=%s interval=%s", interval.contentId, interval.id)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Companion interval preprocessing failed.") from error


def _normalize_companion_interval(interval: CompanionInterval, accessibility_profile, companion_profile) -> IntervalPreparationRequest:
    """Bridge storage-era names while keeping providers and reasoning source-agnostic."""
    interval_number = int(interval.start // 30)
    catalog_scene_id = interval.metadata.get("catalogSceneId")
    return IntervalPreparationRequest(
        movie_id=interval.contentId,
        interval_id=f"{interval.contentId}:interval:{interval_number}",
        interval_number=interval_number,
        interval_start=interval.start,
        interval_end=interval.end,
        timestamp_seconds=interval.timestamp,
        catalog_scene_id=catalog_scene_id if isinstance(catalog_scene_id, str) else None,
        image=interval.image,
        accessibility_profile=accessibility_profile,
        companion_profile=companion_profile,
    )
