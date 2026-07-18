"""Development-only diagnostics and cache reset endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status

from config import Settings, get_settings
from models.knowledge_store import KnowledgeStore
from services.response_cache import ResponseCache
from services.frame_validation import clear_frame_diagnostics, latest_frame_diagnostics

router = APIRouter(prefix="/api/debug", tags=["debug"])


def _debug_only(settings: Settings = Depends(get_settings)) -> None:
    if settings.environment.lower() not in {"development", "dev", "test", "testing"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _semantic_store() -> KnowledgeStore:
    """Defer app imports so this development router has no circular import."""
    from app import get_knowledge_store
    return get_knowledge_store()


def _reasoning_cache() -> ResponseCache:
    from app import get_response_cache
    return get_response_cache()


@router.get("/frame", dependencies=[Depends(_debug_only)])
def frame() -> dict[str, object]:
    return latest_frame_diagnostics()


def _record_or_404(movie_id: str, semantic_store: KnowledgeStore):
    record = semantic_store.get(movie_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No semantic record exists for this movie")
    return record


@router.get("/movies/{movie_id}/knowledge", dependencies=[Depends(_debug_only)])
def knowledge_debug(movie_id: str, semantic_store: KnowledgeStore = Depends(_semantic_store)) -> dict[str, object]:
    """Development-only complete semantic-memory record, including raw observations."""
    return _record_or_404(movie_id, semantic_store).model_dump(mode="json")


@router.get("/movies/{movie_id}/observations", dependencies=[Depends(_debug_only)])
def observations_debug(movie_id: str, semantic_store: KnowledgeStore = Depends(_semantic_store)) -> dict[str, object]:
    """Development-only raw Florence, YOLO, and Grounding DINO evidence."""
    record = _record_or_404(movie_id, semantic_store)
    return {"movie_id": movie_id, "observations": [item.model_dump(mode="json") for item in record.knowledge.observations]}


@router.get("/movies/{movie_id}/claims", dependencies=[Depends(_debug_only)])
def claims_debug(movie_id: str, semantic_store: KnowledgeStore = Depends(_semantic_store)) -> dict[str, object]:
    """Development-only provenance-backed semantic graph claims."""
    record = _record_or_404(movie_id, semantic_store)
    return {"movie_id": movie_id, "claims": [item.model_dump(mode="json") for item in record.knowledge.semantic_claims]}


@router.delete("/cache", dependencies=[Depends(_debug_only)])
def clear_cache(
    semantic_store: KnowledgeStore = Depends(_semantic_store),
    response_cache: ResponseCache = Depends(_reasoning_cache),
) -> dict[str, str]:
    """Clear semantic maps (including anchors/embeddings) and in-memory reasoning output."""
    semantic_store.clear()
    response_cache.clear()
    clear_frame_diagnostics()
    return {"status": "cleared"}
