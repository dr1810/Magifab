"""Face-verification endpoint backed only by enrolled Semantic Movie Knowledge references."""
from fastapi import APIRouter, Depends

from app import get_face_verification_service
from config import Settings, get_settings
from schemas.face_verification import FaceVerificationRequest, FaceVerificationResponse
from services.face_verification import FaceVerificationService
from utils.image import decode_base64_image

router = APIRouter(prefix="/api/v1", tags=["face verification"])


@router.post("/face-verification", response_model=FaceVerificationResponse)
def verify_faces(
    request: FaceVerificationRequest,
    settings: Settings = Depends(get_settings),
    service: FaceVerificationService = Depends(get_face_verification_service),
) -> FaceVerificationResponse:
    """Generate face embeddings and verify only against supplied, enrolled movie knowledge."""
    return service.verify(decode_base64_image(request.image, settings), request.knowledge)
