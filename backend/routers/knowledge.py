"""Versioned knowledge-store and retrieval endpoints; no model or GPT work occurs here."""
from fastapi import APIRouter, Depends, HTTPException, status

from app import get_knowledge_retriever, get_knowledge_store
from models.knowledge_store import KnowledgeStore
from schemas.knowledge import KnowledgeRecord, KnowledgeRetrievalRequest, KnowledgeRetrievalResult, SemanticMovieKnowledge
from services.knowledge_retriever import KnowledgeRetriever

router = APIRouter(prefix="/api/v1/knowledge", tags=["semantic movie knowledge"])


@router.put("/{movie_id}", response_model=KnowledgeRecord)
def save_knowledge(
    movie_id: str,
    knowledge: SemanticMovieKnowledge,
    store: KnowledgeStore = Depends(get_knowledge_store),
) -> KnowledgeRecord:
    """Create a record or atomically store the next revision of a movie knowledge graph."""
    if movie_id != knowledge.movie_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="movie_id path and knowledge.movie_id must match")
    return store.save(knowledge)


@router.get("/{movie_id}", response_model=KnowledgeRecord)
def get_knowledge(movie_id: str, store: KnowledgeStore = Depends(get_knowledge_store)) -> KnowledgeRecord:
    record = store.get(movie_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="movie knowledge was not found")
    return record


@router.post("/retrieve", response_model=KnowledgeRetrievalResult)
def retrieve_knowledge(
    request: KnowledgeRetrievalRequest,
    retriever: KnowledgeRetriever = Depends(get_knowledge_retriever),
) -> KnowledgeRetrievalResult:
    """Retrieve knowledge and the current scene/timeline slice; a miss is a normal response."""
    return retriever.retrieve(request)
