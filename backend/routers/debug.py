"""Development-only diagnostics and cache reset endpoints."""
from fastapi import APIRouter, Depends

from models.knowledge_store import KnowledgeStore
from services.response_cache import ResponseCache
from services.frame_validation import latest_frame_diagnostics

router = APIRouter(prefix="/api/debug", tags=["debug"])


def _semantic_store() -> KnowledgeStore:
    """Defer app imports so this development router has no circular import."""
    from app import get_knowledge_store
    return get_knowledge_store()


def _reasoning_cache() -> ResponseCache:
    from app import get_response_cache
    return get_response_cache()


@router.get("/frame")
def frame() -> dict[str, object]:
    return latest_frame_diagnostics()


@router.delete("/cache")
def clear_cache(
    semantic_store: KnowledgeStore = Depends(_semantic_store),
    response_cache: ResponseCache = Depends(_reasoning_cache),
) -> dict[str, str]:
    """Clear semantic maps (including anchors/embeddings) and in-memory reasoning output."""
    semantic_store.clear()
    response_cache.clear()
    return {"status": "cleared"}
