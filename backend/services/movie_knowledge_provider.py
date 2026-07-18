"""Versioned, local authoritative knowledge for supported movies.

The provider is intentionally read-only at request time. A catalog document is
loaded once per process, normalized into ``SemanticMovieKnowledge``, and then
merged with that movie's isolated runtime record by the expansion engine.
Network retrieval belongs in an offline ingestion job, never in ``/prepare``.
"""
from copy import deepcopy
import json
import logging
from pathlib import Path
from threading import Lock

from schemas.knowledge import SemanticMovieKnowledge
from services.semantic_claim_audit import log_claims

logger = logging.getLogger(__name__)


class MovieKnowledgeProvider:
    """Loads trusted, versioned catalog entries once and returns safe copies."""

    def __init__(self, catalog_dir: Path | None = None):
        self._catalog_dir = catalog_dir or Path(__file__).resolve().parent.parent / "data" / "movie_knowledge"
        self._cache: dict[str, SemanticMovieKnowledge | None] = {}
        self._lock = Lock()

    def get(self, movie_id: str) -> SemanticMovieKnowledge | None:
        """Return a catalog entry for exactly one movie, without cross-movie fallbacks."""
        key = _normalize_movie_id(movie_id)
        with self._lock:
            if key not in self._cache:
                path = self._catalog_dir / f"{key}.json"
                if path.is_file():
                    knowledge = SemanticMovieKnowledge.model_validate_json(path.read_text(encoding="utf-8"))
                    if knowledge.movie_id != movie_id:
                        raise ValueError(
                            f"catalog movie_id mismatch: requested={movie_id!r} catalog={knowledge.movie_id!r}"
                        )
                    self._cache[key] = knowledge
                    logger.info(
                        "[TRACE][MOVIE_KNOWLEDGE] loaded=yes movie=%s title=%r version=%d source=%s",
                        movie_id, knowledge.official_title, knowledge.movie_knowledge_version, path.name,
                    )
                else:
                    self._cache[key] = None
                    logger.info("[TRACE][MOVIE_KNOWLEDGE] loaded=no movie=%s reason=unsupported_movie", movie_id)
            cached = self._cache[key]
        # Pydantic's deep copy ensures runtime merging cannot mutate a singleton
        # catalog object and leak it to another request.
        result = cached.model_copy(deep=True) if cached is not None else None
        if result is not None:
            log_claims("MovieKnowledgeProvider", result.semantic_claims, movie_id=result.movie_id)
        return result


def _normalize_movie_id(movie_id: str) -> str:
    return "".join(character.lower() for character in movie_id if character.isalnum())
