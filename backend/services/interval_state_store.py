"""Durable, immutable snapshots produced by movie preprocessing.

This is deliberately separate from the semantic timeline.  The timeline is an
internal reasoning aid; the interval store is the playback contract.
"""
from hashlib import sha256
import logging
from pathlib import Path
from threading import Lock

from schemas.interval_state import IntervalState, IntervalTimelineMemory

logger = logging.getLogger(__name__)


class IntervalStateRepository:
    """Persist and retrieve exactly one complete precomputed 30-second snapshot."""

    def __init__(self, root: Path, semantic_cache_version: int, interval_seconds: int = 30):
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
            path = self._path(state.metadata.movie_id, state.metadata.interval_number)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(path)
        logger.info("[INTERVAL_CREATED] movie=%s interval=%d start=%.2f end=%.2f", state.metadata.movie_id, state.metadata.interval_number, state.metadata.start_time, state.metadata.end_time)
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

    def list_movie_states(self, movie_id: str) -> list[IntervalState]:
        """Return the completed work's immutable timeline for answer retrieval."""
        return self._movie_states(movie_id)

    def reset_movie(self, movie_id: str) -> None:
        """Discard old snapshots by path, never by schema deserialization."""
        removed = 0
        with self._lock:
            if not self._root.is_dir():
                return
            movie_root = self._movie_root(movie_id)
            if movie_root.is_dir():
                for path in movie_root.glob("*.json"):
                    path.unlink()
                    removed += 1
                movie_root.rmdir()
            # Legacy snapshots were stored as opaque hashes in a flat
            # directory. Their movie ID cannot be known safely without
            # parsing an obsolete schema, so discard them blindly once.
            for path in self._root.glob("*.json"):
                path.unlink()
                removed += 1
        logger.info("[INTERVAL CACHE RESET] movie=%s removed=%d schema_deserialization=no", movie_id, removed)

    def finalize_movie(self, movie_id: str) -> None:
        """Link adjacent, already-computed interval events without reasoning.

        This runs only after the chronological preprocessing pass. It fills
        previous/next timeline references from real neighboring snapshots and
        never asks a model to predict or synthesize a story event.
        """
        states = self._movie_states(movie_id)
        for index, state in enumerate(states):
            prior = states[index - 1] if index else None
            following = states[index + 1] if index + 1 < len(states) else None
            current = _current_event(state)
            timeline = state.timelineMemory.model_copy(update={
                "previous_event": state.timelineMemory.previous_event or (_current_event(prior) if prior else None),
                "current_event": current,
                "next_event": state.timelineMemory.next_event or (_current_event(following) if following else None),
                "is_movie_start": prior is None,
                "is_movie_end": following is None,
            })
            finalized = state.model_copy(update={"timelineMemory": timeline})
            self.save(finalized)
        logger.info("[INTERVAL FINALIZATION] movie=%s intervals=%d", movie_id, len(states))

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
            raise ValueError("IntervalState must use the fixed 30-second interval range")
        expected_id = f"{metadata.movie_id}:interval:{metadata.interval_number}"
        if metadata.interval_id != expected_id:
            raise ValueError("IntervalState id does not match its movie and interval number")

    def summarize(self, movie_id: str, expected_intervals: int | None = None) -> dict[str, int | str | bool]:
        """Validate all persisted snapshots and report aggregate preprocessing health."""
        states = self._movie_states(movie_id)
        reports = [self._presentation_report(state) for state in states]
        result = {
            "movie": movie_id,
            "intervals_generated": len(states),
            "intervals_valid": sum(report["valid"] for report in reports),
            "intervals_invalid": sum(not report["valid"] for report in reports),
            "intervals_missing_prompts": sum(not report["prompts"] for report in reports),
            "intervals_missing_visual_drawer": sum(not report["drawer"] for report in reports),
            "intervals_missing_story_state": sum(not report["story"] for report in reports),
            "intervals_missing_semantic_memory": sum(not report["semantic_memory"] for report in reports),
            "intervals_missing_timeline": sum(not report["timeline"] for report in reports),
            "expected_intervals": expected_intervals if expected_intervals is not None else len(states),
        }
        result["movie_ready_for_playback"] = (
            result["intervals_generated"] == result["expected_intervals"]
            and result["intervals_valid"] == result["expected_intervals"]
        )
        logger.info("[MOVIE PREPROCESSING SUMMARY] %s", result)
        return result

    def _log_validation(self, state: IntervalState) -> None:
        report = self._presentation_report(state)
        logger.info(
            "[INTERVAL_VALIDATED] status=%s movie=%s interval=%d prompts=%s drawer=%s story=%s timeline=%s characters=%s relationships=%s objects=%s memory=%s semantic_memory=%s accessibility=%s scene_summary=%s goal=%s previous_event=%s current_event=%s next_event=%s",
            "PASS" if report["valid"] else "FAIL", state.metadata.movie_id, state.metadata.interval_number,
            report["prompts"], report["drawer"], report["story"], report["timeline"], report["characters"],
            report["relationships"], report["objects"], report["memory"],
            report["semantic_memory"], report["accessibility"],
            report["scene_summary"], report["goal"], report["previous_event"], report["current_event"], report["next_event"],
        )

    @staticmethod
    def _presentation_report(state: IntervalState) -> dict[str, bool]:
        # Validation is structural. Empty prompt/relationship/object lists are
        # legitimate movie facts; only a missing snapshot component fails the
        # preprocessing run. Content counts remain in the interval logs.
        report = {
            "prompts": state.prompts is not None,
            "drawer": state.visualDrawer is not None,
            "story": state.storyState is not None,
            "timeline": state.timelineMemory is not None,
            "characters": state.characters is not None,
            "relationships": state.relationships is not None,
            "objects": state.visualDrawer.objects is not None,
            "memory": state.memory is not None,
            "semantic_memory": state.semanticMemoryBefore is not None and state.semanticMemoryAfter is not None,
            "accessibility": state.accessibilityHints is not None and state.conversationContext is not None,
            "scene_summary": state.storyState is not None,
            "goal": state.storyState is not None,
            "timeline_position": state.timelineMemory is not None,
            "previous_event": state.timelineMemory is not None,
            "current_event": state.timelineMemory is not None,
            "next_event": state.timelineMemory is not None,
        }
        report["valid"] = all(report.values())
        return report

    def _path(self, movie_id: str, interval_number: int) -> Path:
        return self._movie_root(movie_id) / f"{interval_number:08d}.json"

    def _movie_root(self, movie_id: str) -> Path:
        """Movie-scoped paths make schema-blind cache deletion possible."""
        token = sha256(movie_id.encode("utf-8")).hexdigest()
        return self._root / token

    def _movie_states(self, movie_id: str) -> list[IntervalState]:
        states: list[IntervalState] = []
        with self._lock:
            for path in self._movie_root(movie_id).glob("*.json") if self._movie_root(movie_id).is_dir() else ():
                state = IntervalState.model_validate_json(path.read_text(encoding="utf-8"))
                if state.metadata.movie_id == movie_id:
                    states.append(state)
        return sorted(states, key=lambda item: item.metadata.interval_number)


def _current_event(state: IntervalState | None) -> str | None:
    if state is None:
        return None
    return (
        state.timelineMemory.current_event
        or state.storyState.scene_summary
        or next(iter(state.storyState.story_so_far), None)
    )
