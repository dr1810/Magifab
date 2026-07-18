"""Retrieval-first expansion endpoint that runs perception only for a true knowledge miss."""
from fastapi import APIRouter, Depends, HTTPException, status

from app import get_knowledge_expansion_engine
from config import Settings, get_settings
from schemas.knowledge_expansion import KnowledgeExpansionRequest, KnowledgeExpansionResult
from services.knowledge_expansion import KnowledgeExpansionEngine
from utils.image import decode_base64_image_with_size

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge expansion"])


@router.post("/expand", response_model=KnowledgeExpansionResult)
def expand_knowledge(
    request: KnowledgeExpansionRequest,
    settings: Settings = Depends(get_settings),
    engine: KnowledgeExpansionEngine = Depends(get_knowledge_expansion_engine),
) -> KnowledgeExpansionResult:
    """Return a stored scene first; decode an image and run perception only on a scene-level miss."""
    # A frame fingerprint is part of semantic-cache identity. Decode once here
    # so a legacy /expand caller receives the same isolation guarantees as
    # /prepare; model inference remains deferred until after the cache check.
    image = None
    if request.image:
        image, _, frame_hash = decode_base64_image_with_size(request.image, settings)
        request = request.model_copy(update={"frame_hash": frame_hash})
        if not engine.needs_expansion(request):
            image = None
    try:
        return engine.retrieve_or_expand(request, image)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
