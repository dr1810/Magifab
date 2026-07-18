"""Retrieval-first expansion endpoint that runs perception only for a true knowledge miss."""
from fastapi import APIRouter, Depends, HTTPException, status

from app import get_knowledge_expansion_engine
from config import Settings, get_settings
from schemas.knowledge_expansion import KnowledgeExpansionRequest, KnowledgeExpansionResult
from services.knowledge_expansion import KnowledgeExpansionEngine
from utils.image import decode_base64_image

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge expansion"])


@router.post("/expand", response_model=KnowledgeExpansionResult)
def expand_knowledge(
    request: KnowledgeExpansionRequest,
    settings: Settings = Depends(get_settings),
    engine: KnowledgeExpansionEngine = Depends(get_knowledge_expansion_engine),
) -> KnowledgeExpansionResult:
    """Return a stored scene first; decode an image and run perception only on a scene-level miss."""
    # Retrieval is intentionally before image decoding, model loading, or any perception work.
    image = decode_base64_image(request.image, settings) if engine.needs_expansion(request) and request.image else None
    try:
        return engine.retrieve_or_expand(request, image)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
