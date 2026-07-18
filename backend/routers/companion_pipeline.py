"""Retrieval-first runtime endpoint for the full MagiFab backend pipeline."""
import logging
from time import perf_counter
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from adapters.openai_personalizer import PersonalizationConfigurationError, PersonalizationProviderError
from app import get_companion_pipeline_service
from config import Settings, get_settings
from schemas.companion_pipeline import CompanionPipelineRequest, CompanionPipelineResponse, ScenePreparationRequest, ScenePreparationResponse
from services.companion_pipeline import CompanionPipelineService
from services.frame_validation import InvalidFrameError, validate_frame
from utils.image import decode_base64_image_with_size

router = APIRouter(prefix="/api/v1/companion", tags=["companion pipeline"])
logger = logging.getLogger(__name__)


@router.post("/respond", response_model=CompanionPipelineResponse)
def respond(
    request: CompanionPipelineRequest,
    settings: Settings = Depends(get_settings),
    service: CompanionPipelineService = Depends(get_companion_pipeline_service),
) -> CompanionPipelineResponse:
    """Prompt interaction is retrieval-only: no image decoding, perception, or GPT work is allowed."""
    try:
        return service.respond(request)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    except PersonalizationConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GPT personalization is not configured") from error
    except PersonalizationProviderError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GPT personalization is unavailable") from error


@router.post("/prepare", response_model=ScenePreparationResponse)
def prepare_scene(
    request: ScenePreparationRequest,
    settings: Settings = Depends(get_settings),
    service: CompanionPipelineService = Depends(get_companion_pipeline_service),
) -> ScenePreparationResponse:
    """Run perception once for an unknown scene before prompt bubbles become available."""
    started = perf_counter()
    try:
        logger.info("[TRACE][PREPARE] start movie_id=%s scene_id=%s timestamp=%s", request.movie_id, request.scene_id, request.timestamp_seconds)
        decode_started = perf_counter()
        image, file_size, frame_hash = decode_base64_image_with_size(request.image, settings)
        logger.info("[TRACE][FRAME_CAPTURE] executed=yes movie=%s scene=%s frame_hash=%s input_bytes=%d output=%dx%d duration_ms=%.1f", request.movie_id, request.scene_id, frame_hash, file_size, image.width, image.height, (perf_counter() - decode_started) * 1000)
        validation_started = perf_counter()
        validate_frame(
            image,
            file_size=file_size,
            timestamp=request.timestamp_seconds,
            debug_dir=settings.debug_frames_dir,
            movie_id=request.movie_id,
            scene_id=request.scene_id,
            frame_hash=frame_hash,
        )
        logger.info("[TRACE][FRAME_VALIDATION] executed=yes output=valid duration_ms=%.1f", (perf_counter() - validation_started) * 1000)
        response = service.prepare(request, image, frame_hash)
        serialized = response.model_dump(mode="json")
        logger.info(
            "[TRACE][FASTAPI_SERIALIZATION] executed=yes top_level_prompts=%d nested_prompts=%d first_prompt=%s response_list_id=%s dumped_prompt_count=%d dumped_first=%s",
            len(response.prompt_bubbles), len(response.accessibility_content.prompt_bubbles), response.prompt_bubbles[0].title if response.prompt_bubbles else None,
            id(response.prompt_bubbles), len(serialized["prompt_bubbles"]), serialized["prompt_bubbles"][0]["title"] if serialized["prompt_bubbles"] else None,
        )
        logger.info(
            "[TRACE][API_RESPONSE] executed=yes output prompts=%d character_cards=%d relationships=%d duration_ms=%.1f",
            len(response.prompt_bubbles), len(response.visual_drawer.character_cards), len(response.visual_drawer.relationship_summaries), (perf_counter() - started) * 1000,
        )
        return response
    except InvalidFrameError as error:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"error": "invalid_frame", "reason": error.reason})
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
