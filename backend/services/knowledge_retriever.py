"""Retrieval-first service over the knowledge-store interface."""
from models.knowledge_store import KnowledgeStore
from schemas.knowledge import KnowledgeRetrievalRequest, KnowledgeRetrievalResult
from services.movie_knowledge_graph import MovieKnowledgeGraph


class KnowledgeRetriever:
    """Retrieves existing movie knowledge; cache misses remain explicit and do not invoke GPT."""

    def __init__(self, store: KnowledgeStore):
        self._store = store

    def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResult:
        record = self._store.get(request.movie_id)
        if record is None:
            return KnowledgeRetrievalResult(found=False)
        graph = MovieKnowledgeGraph(record.knowledge)
        return KnowledgeRetrievalResult(
            found=True,
            record=record,
            scene_summary=graph.scene(request.scene_id, request.timestamp_seconds),
            timeline_position=graph.timeline_position(request.timestamp_seconds),
        )
