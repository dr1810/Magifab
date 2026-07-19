"""Durable, immutable snapshots produced by movie preprocessing.

This is deliberately separate from the semantic timeline.  The timeline is an
internal reasoning aid; the interval store is the playback contract.
"""
from hashlib import sha256
import logging
from pathlib import Path
from threading import Lock

from schemas.interval_state import IntervalState

logger = logging.getLogger(__name__)


class IntervalStateRepository:
    """Persist and retrieve exactly one precomputed state per 30 second interval."""

    def __init__(self, root: Path, semantic_cache_version: int, interval_seconds: int = 10):
        self._root = root / f"v{semantic_cache_version}" / "interval-states"
        self._version = semantic_cache_version
        self.interval_seconds = interval_seconds
        self._lock = Lock()

    def interval_number(self, timestamp_seconds: float) -> int:
        return int(timestamp_seconds // self.interval_seconds)

    def bounds(self, timestamp_seconds: float) -> tuple[int, float, float]:
        number = self.interval_number(timestamp_seconds)
        start = float(number * self.interval_seconds)
        return number, start, start + self.interval_seconds

    def save(self, state: IntervalState) -> IntervalState:
        self._validate(state)
        with self._lock:
            self._root.mkdir(parents=True, exist_ok=True)
            path = self._path(state.metadata.movie_id, state.metadata.interval_number)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(path)
        self._log_validation(state)
        return state

    def load(self, movie_id: str, timestamp_seconds: float) -> IntervalState | None:
        with self._lock:
            path = self._path(movie_id, self.interval_number(timestamp_seconds))
            if not path.is_file():
                return None
            state = IntervalState.model_validate_json(path.read_text(encoding="utf-8"))
        # Never approximate across a boundary: a corrupted/wrong cache entry is
        # a preprocessing miss, not permission to regenerate during playback.
        if state.metadata.movie_id != movie_id:
            return None
        if not (state.metadata.start_time <= timestamp_seconds < (state.metadata.end_time or float("inf"))):
            return None
        return state

    def load_interval(self, movie_id: str, interval_number: int) -> IntervalState | None:
        """Direct immutable lookup; no temporal ordering is inferred or stored."""
        with self._lock:
            path = self._path(movie_id, interval_number)
            if not path.is_file():
                return None
            state = IntervalState.model_validate_json(path.read_text(encoding="utf-8"))
        self._validate(state)
        return state if state.metadata.movie_id == movie_id else None

    def reset_movie(self, movie_id: str) -> None:
        """Remove only this movie's obsolete snapshots before a fresh run."""
        removed = 0
        with self._lock:
            if not self._root.is_dir():
                return
            for path in self._root.glob("*.json"):
                state = IntervalState.model_validate_json(path.read_text(encoding="utf-8"))
                if state.metadata.movie_id == movie_id:
                    path.unlink()
                    removed += 1
        logger.info("[INTERVAL CACHE RESET] movie=%s removed=%d", movie_id, removed)

    def _validate(self, state: IntervalState) -> None:
        metadata = state.metadata
        if not metadata.interval_id or metadata.knowledge_revision < 1:
            raise ValueError("invalid IntervalState metadata")
        expected_number = self.interval_number(metadata.start_time)
        if metadata.interval_number != expected_number:
            raise ValueError("IntervalState interval number does not match its start time")
        if metadata.end_time is None or metadata.end_time <= metadata.start_time:
            raise ValueError("IntervalState has an invalid interval range")
        if metadata.end_time > metadata.start_time + self.interval_seconds:
            raise ValueError("IntervalState exceeds its fixed interval range")
        if metadata.end_time != metadata.start_time + self.interval_seconds:
            raise ValueError("IntervalState must use the fixed 10-second interval range")
        expected_id = f"{metadata.movie_id}:interval:{metadata.interval_number}"
        if metadata.interval_id != expected_id:
            raise ValueError("IntervalState id does not match its movie and interval number")

    def summarize(self, movie_id: str, expected_intervals: int | None = None) -> dict[str, int | str]:
        """Validate all persisted snapshots and report aggregate preprocessing health."""
        states: list[IntervalState] = []
        with self._lock:
            for path in self._root.glob("*.json") if self._root.is_dir() else ():
                state = IntervalState.model_validate_json(path.read_text(encoding="utf-8"))
                if state.metadata.movie_id == movie_id:
                    states.append(state)
        reports = [self._presentation_report(state) for state in states]
        result = {
            "movie": movie_id,
            "intervals_generated": len(states),
            "intervals_valid": sum(report["valid"] for report in reports),
            "intervals_missing_prompts": sum(not report["prompts"] for report in reports),
            "intervals_missing_visual_drawer": sum(not report["drawer"] for report in reports),
            "intervals_missing_story_state": sum(not report["story"] for report in reports),
            "expected_intervals": expected_intervals if expected_intervals is not None else len(states),
        }
        logger.info("[MOVIE PREPROCESSING SUMMARY] %s", result)
        return result

    def _log_validation(self, state: IntervalState) -> None:
        report = self._presentation_report(state)
        logger.info(
            "[INTERVAL_VALIDATED] status=%s movie=%s interval=%d prompts=%s drawer=%s story=%s timeline=%s characters=%s relationships=%s objects=%s memory=%s semantic_memory=%s accessibility=%s",
            "PASS" if report["valid"] else "FAIL", state.metadata.movie_id, state.metadata.interval_number,
            report["prompts"], report["drawer"], report["story"], report["timeline"], report["characters"],
            report["relationships"], report["objects"], report["memory"],
            report["semantic_memory"], report["accessibility"],
        )

    @staticmethod
    def _presentation_report(state: IntervalState) -> dict[str, bool]:
        drawer = state.visualDrawer
        report = {
            "prompts": bool(state.prompts.prompt_bubbles),
            "story": bool(state.storyState.scene_summary or state.storyState.story_so_far),
            "timeline": bool(drawer.timeline), "characters": bool(state.characters),
            "relationships": bool(state.relationships or drawer.relationships),
            "objects": bool(drawer.objects), "memory": bool(state.memory or drawer.memory),
            "cause_effect": bool(drawer.cause_effect),
            "emotion": bool(drawer.emotion or state.accessibilityHints.emotions),
            "semantic_memory": bool(state.semanticMemoryAfter.story_events or state.semanticMemoryAfter.active_characters),
            "accessibility": bool(state.conversationContext.scene_explanation and state.accessibilityHints),
        }
        report["drawer"] = all(report[name] for name in ("timeline", "relationships", "objects", "memory", "cause_effect", "emotion"))
        report["valid"] = all(report.values())
        return report

    def _path(self, movie_id: str, interval_number: int) -> Path:
        token = f"{movie_id}:{interval_number}:{self._version}"
        return self._root / f"{sha256(token.encode('utf-8')).hexdigest()}.json"
