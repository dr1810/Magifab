"""Versioned HTTP endpoint for generic object detection."""
from fastapi import APIRouter, Depends

from app import get_object_detection_service
from config import Settings, get_settings
from schemas.detection import DetectionRequest, DetectionResponse
from services.object_detection import ObjectDetectionService
from utils.image import decode_base64_image

router = APIRouter(prefix="/api/v1", tags=["object detection"])


@router.post("/detect", response_model=DetectionResponse)
def detect(
    request: DetectionRequest,
    settings: Settings = Depends(get_settings),
    service: ObjectDetectionService = Depends(get_object_detection_service),
) -> DetectionResponse:
    """Detect classes and boxes only; no character identity or semantic interpretation."""
    return service.detect(decode_base64_image(request.image, settings))
