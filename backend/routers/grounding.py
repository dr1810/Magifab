"""On-demand text-guided object-localization endpoint."""
from fastapi import APIRouter, Depends

from app import get_object_grounding_service
from config import Settings, get_settings
from schemas.grounding import GroundingRequest, GroundingResponse
from services.object_grounding import ObjectGroundingService
from utils.image import decode_base64_image

router = APIRouter(prefix="/api/v1", tags=["object grounding"])


@router.post("/ground", response_model=GroundingResponse)
def ground(
    request: GroundingRequest,
    settings: Settings = Depends(get_settings),
    service: ObjectGroundingService = Depends(get_object_grounding_service),
) -> GroundingResponse:
    """Locate only requested visual-object phrases in the supplied image."""
    return service.locate(decode_base64_image(request.image, settings), request.queries)
