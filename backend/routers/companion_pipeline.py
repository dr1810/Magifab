"""Retrieval-first runtime endpoint for the full MagiFab backend pipeline."""
import logging
from time import perf_counter
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from adapters.openai_personalizer import PersonalizationConfigurationError, PersonalizationProviderError
from app import get_companion_pipeline_service
from config import Settings, get_settings
from schemas.companion_pipeline import CompanionPipelineRequest, CompanionPipelineResponse, IntervalPreparationRequest, IntervalPreparationResponse, PreprocessingCompletionRequest
from services.companion_pipeline import CompanionPipelineService
from services.frame_validation import InvalidFrameError, validate_frame
from utils.image import decode_base64_image_with_size

router = APIRouter(prefix="/api/v1/companion", tags=["companion pipeline"])
logger = logging.getLogger(__name__)


@router.post("/preprocessing/complete")
def complete_preprocessing(
    request: PreprocessingCompletionRequest,
    service: CompanionPipelineService = Depends(get_companion_pipeline_service),
) -> dict[str, int | str]:
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


@router.post("/prepare", response_model=IntervalPreparationResponse)
def prepare_interval(
    request: IntervalPreparationRequest,
    settings: Settings = Depends(get_settings),
    service: CompanionPipelineService = Depends(get_companion_pipeline_service),
) -> IntervalPreparationResponse:
    """Run perception once for a fixed interval before playback is available."""
    started = perf_counter()
    try:
        logger.info("[TRACE][PREPARE] start movie_id=%s interval_id=%s timestamp=%s", request.movie_id, request.interval_id, request.timestamp_seconds)
        decode_started = perf_counter()
        image, file_size, frame_hash = decode_base64_image_with_size(request.image, settings)
        logger.info("[TRACE][FRAME_CAPTURE] executed=yes movie=%s interval=%s frame_hash=%s input_bytes=%d output=%dx%d duration_ms=%.1f", request.movie_id, request.interval_id, frame_hash, file_size, image.width, image.height, (perf_counter() - decode_started) * 1000)
        validation_started = perf_counter()
        validate_frame(
            image,
            file_size=file_size,
            timestamp=request.timestamp_seconds,
            debug_dir=settings.debug_frames_dir,
            movie_id=request.movie_id,
            scene_id=request.interval_id,
            frame_hash=frame_hash,
        )
        logger.info("[TRACE][FRAME_VALIDATION] executed=yes output=valid duration_ms=%.1f", (perf_counter() - validation_started) * 1000)
        response = service.prepare(request, image, frame_hash)
        serialized = response.model_dump(mode="json")
        logger.info(
            "[TRACE][FASTAPI_SERIALIZATION] executed=yes interval_prompts=%d first_prompt=%s response_list_id=%s dumped_prompt_count=%d dumped_first=%s",
            len(response.prompts.prompt_bubbles), response.prompts.prompt_bubbles[0].label if response.prompts.prompt_bubbles else None,
            id(response.prompts.prompt_bubbles), len(serialized["prompts"]["prompt_bubbles"]), serialized["prompts"]["prompt_bubbles"][0]["label"] if serialized["prompts"]["prompt_bubbles"] else None,
        )
        logger.info(
            "[TRACE][API_RESPONSE] executed=yes output interval_prompts=%d characters=%d relationships=%d duration_ms=%.1f",
            len(response.prompts.prompt_bubbles), len(response.characters), len(response.relationships), (perf_counter() - started) * 1000,
        )
        return response
    except InvalidFrameError as error:
        logger.warning("[INTERVAL PREPROCESSING] rejected frame=%s", error.reason)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A valid interval frame is required for preprocessing.") from error
    except (ValueError, AssertionError) as error:
        logger.exception("[INTERVAL PREPROCESSING] failed")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Interval preprocessing failed.") from error
