"""Versioned HTTP endpoint for perception-only scene understanding."""
from fastapi import APIRouter, Depends

from app import get_vision_understanding_service
from config import Settings, get_settings
from schemas.understanding import UnderstandingRequest, UnderstandingResponse
from services.vision_understanding import VisionUnderstandingService
from utils.image import decode_base64_image

router = APIRouter(prefix="/api/v1", tags=["vision understanding"])


@router.post("/understand", response_model=UnderstandingResponse)
def understand(
    request: UnderstandingRequest,
    settings: Settings = Depends(get_settings),
    service: VisionUnderstandingService = Depends(get_vision_understanding_service),
) -> UnderstandingResponse:
    """Describe visible scene evidence only; no character identity or semantic matching."""
    return service.understand(decode_base64_image(request.image, settings))
