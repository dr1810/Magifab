"""Versioned endpoint for structured semantic matching without language-model reasoning."""
from fastapi import APIRouter, Depends

from app import get_semantic_matching_service
from schemas.matching import SemanticMatchRequest, SemanticMatchResult
from services.semantic_matching import SemanticMatchingService

router = APIRouter(prefix="/api/v1", tags=["semantic matching"])


@router.post("/match", response_model=SemanticMatchResult)
def match(
    request: SemanticMatchRequest,
    service: SemanticMatchingService = Depends(get_semantic_matching_service),
) -> SemanticMatchResult:
    """Compare supplied perception with supplied movie knowledge; no GPT or inference occurs."""
    return service.match(request.scene, request.knowledge)
