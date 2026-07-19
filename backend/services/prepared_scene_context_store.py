"""Durable lookup for the semantic context produced during /prepare."""
from hashlib import sha256
from pathlib import Path
from threading import Lock

from schemas.prepared_scene_context import PreparedSceneContext


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
            self._root.mkdir(parents=True, exist_ok=True)
            path = self._path(context.movie_id, context.scene_id, context.timestamp_seconds)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(context.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(path)
        return context

    def load(self, *, movie_id: str, scene_id: str | None, timestamp_seconds: float, max_delta_seconds: float) -> PreparedSceneContext | None:
        if not self._root.is_dir():
            return None
        candidates: list[PreparedSceneContext] = []
        with self._lock:
            for path in self._root.glob("*.json"):
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
        candidates.sort(key=lambda item: (item.scene_id != scene_id, abs(item.timestamp_seconds - timestamp_seconds)))
        return candidates[0]

    def _path(self, movie_id: str, scene_id: str, timestamp_seconds: float) -> Path:
        token = f"{movie_id}:{scene_id}:{timestamp_seconds:.3f}"
        return self._root / f"{sha256(token.encode('utf-8')).hexdigest()}.json"
