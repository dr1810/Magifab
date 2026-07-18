"""Retrieval-first service over the knowledge-store interface."""
from models.knowledge_store import KnowledgeStore
from schemas.knowledge import KnowledgeRetrievalRequest, KnowledgeRetrievalResult
from services.movie_knowledge_graph import MovieKnowledgeGraph
from services.semantic_claim_audit import log_claims


class KnowledgeRetriever:
    """Retrieves existing movie knowledge; cache misses remain explicit and do not invoke GPT."""

    def __init__(self, store: KnowledgeStore):
        self._store = store

    def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResult:
        record = self._store.get(request.movie_id)
        if record is None:
            return KnowledgeRetrievalResult(found=False)
        graph = MovieKnowledgeGraph(record.knowledge)
        log_claims("KnowledgeRetriever.record", record.knowledge.semantic_claims, movie_id=record.movie_id)
        resolved_scene = graph.scene(request.scene_id, request.timestamp_seconds)
        log_claims(
            "KnowledgeRetriever.scene",
            [claim for claim in record.knowledge.semantic_claims if resolved_scene and claim.scene_id == resolved_scene.scene_id],
            movie_id=record.movie_id,
            scene_id=resolved_scene.scene_id if resolved_scene else request.scene_id,
        )
        return KnowledgeRetrievalResult(
            found=True,
            record=record,
            scene_summary=resolved_scene,
            timeline_position=graph.timeline_position(request.timestamp_seconds),
        )
