"""Atomic JSON-file implementation of the semantic knowledge storage contract."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from threading import Lock

from models.knowledge_store import KnowledgeStore
from schemas.knowledge import KnowledgeRecord, SemanticMovieKnowledge


class FileKnowledgeStore(KnowledgeStore):
    """Local persistence suitable for development and replaceable by a database-backed store."""

    def __init__(self, root: Path):
        self._root = root
        self._lock = Lock()

    def exists(self, movie_id: str) -> bool:
        return self._path(movie_id).is_file()

    def get(self, movie_id: str) -> KnowledgeRecord | None:
        path = self._path(movie_id)
        if not path.is_file():
            return None
        return KnowledgeRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, knowledge: SemanticMovieKnowledge) -> KnowledgeRecord:
        """Write a new immutable revision with an atomic replace operation."""
        with self._lock:
            existing = self.get(knowledge.movie_id)
            now = datetime.now(timezone.utc)
            revision = (existing.revision + 1) if existing else 1
            versioned_knowledge = knowledge.model_copy(update={"version": revision})
            record = KnowledgeRecord(
                movie_id=knowledge.movie_id,
                revision=revision,
                created_at=existing.created_at if existing else now,
                updated_at=now,
                knowledge=versioned_knowledge,
            )
            self._root.mkdir(parents=True, exist_ok=True)
            path = self._path(knowledge.movie_id)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(record.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(path)
            return record

    def _path(self, movie_id: str) -> Path:
        """Hash externally supplied IDs so they can never become path segments."""
        digest = hashlib.sha256(movie_id.encode("utf-8")).hexdigest()
        return self._root / f"{digest}.json"
