"""Durable lookup for the semantic context produced during /prepare."""
from hashlib import sha256
import logging
from pathlib import Path
from threading import Lock

from schemas.prepared_scene_context import PreparedSceneContext

logger = logging.getLogger(__name__)


class PreparedSceneContextStore:
    """Stores immutable prepared contexts separately from movie knowledge facts."""

    def __init__(self, root: Path, semantic_cache_version: int):
        self._root = root / f"v{semantic_cache_version}" / "prepared-contexts"
        self._version = semantic_cache_version
        self._lock = Lock()

    def save(self, context: PreparedSceneContext) -> PreparedSceneContext:
        if context.semantic_cache_version != self._version:
            raise ValueError("prepared context cache version mismatch")
        with self._lock:
            path = self._path(context.movie_id, context.interval_id, context.timestamp_seconds)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(context.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(path)
        return context

    def load(self, *, movie_id: str, interval_id: str | None, timestamp_seconds: float, max_delta_seconds: float) -> PreparedSceneContext | None:
        movie_root = self._movie_root(movie_id)
        if not movie_root.is_dir():
            return None
        candidates: list[PreparedSceneContext] = []
        with self._lock:
            for path in movie_root.glob("*.json"):
                item = PreparedSceneContext.model_validate_json(path.read_text(encoding="utf-8"))
                if item.movie_id != movie_id or item.semantic_cache_version != self._version:
                    continue
                if abs(item.timestamp_seconds - timestamp_seconds) > max_delta_seconds:
                    continue
                candidates.append(item)
        if not candidates:
            return None
        # Prefer the caller's exact canonical scene ID, otherwise timestamp is
        # authoritative for callers that use a UI alias rather than catalog ID.
        candidates.sort(key=lambda item: (item.interval_id != interval_id, abs(item.timestamp_seconds - timestamp_seconds)))
        return candidates[0]

    def reset_movie(self, movie_id: str) -> None:
        """Delete prepared-context cache files without parsing old schemas."""
        removed = 0
        with self._lock:
            movie_root = self._movie_root(movie_id)
            if movie_root.is_dir():
                for path in movie_root.glob("*.json"):
                    path.unlink()
                    removed += 1
                movie_root.rmdir()
            # Legacy prepared-context files were opaque flat hashes. They are
            # preprocessing-only, so discard them rather than deserialize.
            if self._root.is_dir():
                for path in self._root.glob("*.json"):
                    path.unlink()
                    removed += 1
        logger.info("[PREPARED CONTEXT RESET] movie=%s removed=%d schema_deserialization=no", movie_id, removed)

    def _path(self, movie_id: str, interval_id: str, timestamp_seconds: float) -> Path:
        token = f"{movie_id}:{interval_id}:{timestamp_seconds:.3f}"
        return self._movie_root(movie_id) / f"{sha256(token.encode('utf-8')).hexdigest()}.json"

    def _movie_root(self, movie_id: str) -> Path:
        return self._root / sha256(movie_id.encode("utf-8")).hexdigest()
