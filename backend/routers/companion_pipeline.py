"""Retrieval-first runtime endpoint for the full MagiFab backend pipeline."""
import logging
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
    try:
        logger.info("[PREPARE] movie_id: %s", request.movie_id)
        logger.info("[FRAME] timestamp: %s", request.timestamp_seconds)
        image, file_size = decode_base64_image_with_size(request.image, settings)
        validate_frame(
            image,
            file_size=file_size,
            timestamp=request.timestamp_seconds,
            debug_dir=settings.debug_frames_dir,
            scene_id=request.scene_id,
        )
        return service.prepare(request, image)
    except InvalidFrameError as error:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"error": "invalid_frame", "reason": error.reason})
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
