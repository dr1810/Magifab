"""Retrieval-first runtime endpoint for the full MagiFab backend pipeline."""
from fastapi import APIRouter, Depends, HTTPException, status

from adapters.openai_personalizer import PersonalizationConfigurationError, PersonalizationProviderError
from app import get_companion_pipeline_service
from config import Settings, get_settings
from schemas.companion_pipeline import CompanionPipelineRequest, CompanionPipelineResponse
from services.companion_pipeline import CompanionPipelineService
from utils.image import decode_base64_image

router = APIRouter(prefix="/api/v1/companion", tags=["companion pipeline"])


@router.post("/respond", response_model=CompanionPipelineResponse)
def respond(
    request: CompanionPipelineRequest,
    settings: Settings = Depends(get_settings),
    service: CompanionPipelineService = Depends(get_companion_pipeline_service),
) -> CompanionPipelineResponse:
    """Retrieve knowledge first; decode a frame only for a missing scene, then return cached personalized wording."""
    needs_image = service.needs_perception(request)
    image = decode_base64_image(request.image, settings) if needs_image and request.image else None
    try:
        return service.respond(request, image)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    except PersonalizationConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GPT personalization is not configured") from error
    except PersonalizationProviderError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GPT personalization is unavailable") from error
