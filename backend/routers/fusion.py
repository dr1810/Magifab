"""Versioned endpoint that fuses existing perception outputs without running models."""
from fastapi import APIRouter, Depends

from app import get_perception_fusion_service
from schemas.fusion import FusionRequest, UnifiedSceneRepresentation
from services.perception_fusion import PerceptionFusionService

router = APIRouter(prefix="/api/v1", tags=["perception fusion"])


@router.post("/fuse", response_model=UnifiedSceneRepresentation)
def fuse(
    request: FusionRequest,
    service: PerceptionFusionService = Depends(get_perception_fusion_service),
) -> UnifiedSceneRepresentation:
    """Fuse supplied perception evidence; no model inference occurs here."""
    return service.fuse_current_outputs(request.object_detection, request.scene_understanding, request.grounding, request.face_verification)
