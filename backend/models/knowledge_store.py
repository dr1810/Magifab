"""Storage contract for versioned semantic movie knowledge."""
from abc import ABC, abstractmethod

from schemas.knowledge import KnowledgeRecord, SemanticMovieKnowledge


class KnowledgeStore(ABC):
    """Persistence boundary; replace file storage with a database without changing retrieval."""

    @abstractmethod
    def exists(self, movie_id: str) -> bool:
        """Return whether a record exists for a movie."""

    @abstractmethod
    def get(self, movie_id: str) -> KnowledgeRecord | None:
        """Return a record or no result when knowledge has not been stored."""

    @abstractmethod
    def save(self, knowledge: SemanticMovieKnowledge) -> KnowledgeRecord:
        """Create or version an atomic record for a movie."""
