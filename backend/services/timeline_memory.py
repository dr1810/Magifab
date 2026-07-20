"""Preprocessing semantic timeline used to assemble IntervalStates."""
from __future__ import annotations

from hashlib import sha256
import logging
from pathlib import Path
from threading import Lock

from schemas.story_state import StoryEvent, StoryState
from schemas.timeline_memory import TimelineInterval, TimelineMemory, TimelineState
from services.drawer_state_builder import DrawerStateBuilder
from services.prompt_scheduler import PromptScheduler
from services.semantic_state_resolver import SemanticStateResolver

logger = logging.getLogger(__name__)


class TimelineMemoryService:
    """Writes one fixed interval snapshot for every preprocessing step."""

    def __init__(self, root: Path, semantic_cache_version: int):
        self._root = root / f"v{semantic_cache_version}" / "timeline-memory"
        self._lock = Lock()
        self._drawer = DrawerStateBuilder()
        self._prompts = PromptScheduler()
        self._resolver = SemanticStateResolver()

    def write_change(self, state_before: StoryState, state_after: StoryState, events: list[StoryEvent]) -> TimelineMemory:
        if not events:
            return self.get(state_after.movie_id)
        timestamp = min(event.timestamp_start for event in events)
        with self._lock:
            memory = self._repair(self._load(state_after.movie_id))
            event_ids = [event.event_id for event in events]
            if any(set(item.triggering_event_ids) == set(event_ids) for item in memory.intervals):
                return memory
            # A semantic interval ends at the next semantic change, never at a
            # fixed sliding-window boundary.
            for interval in memory.intervals:
                if interval.end_timestamp is None and interval.start_timestamp <= timestamp:
                    interval.end_timestamp = timestamp
                    interval.state.drawer_state.end_timestamp = timestamp
            _expire_prompts(memory, events, timestamp)
            scheduled = self._prompts.schedule(state_after, events)
            active_prompts = _unique_active_prompts(memory, timestamp)
            state = TimelineState(timestamp=timestamp, story_state=state_after, prompts=[*active_prompts, *scheduled], drawer_state=self._drawer.build(state_after, timestamp))
            interval = TimelineInterval(interval_id=f"{state_after.movie_id}:{timestamp:.3f}:{event_ids[0]}", start_timestamp=timestamp, triggering_event_ids=event_ids, importance=max(event.importance_score for event in events), story_state_before=state_before, story_state_after=state_after, state=state)
            memory.intervals.append(interval)
            memory.intervals.sort(key=lambda item: item.start_timestamp)
            self._save(self._repair(memory))
        logger.info("[TIMELINE MEMORY] movie=%s interval=%s events=%d timestamp=%.2f", state_after.movie_id, interval.interval_id, len(events), timestamp)
        return memory

    def write_interval(
        self,
        state_before: StoryState,
        state_after: StoryState,
        events: list[StoryEvent],
        *,
        interval_id: str,
        interval_start: float,
        interval_end: float,
    ) -> TimelineState:
        """Freeze timeline/prompt/drawer data at every fixed interval.

        Empty semantic intervals are meaningful: they retain the prior story
        state rather than becoming a gap or expiring the current prompt set.
        """
        with self._lock:
            memory = self._repair(self._load(state_after.movie_id))
            memory.intervals = [item for item in memory.intervals if item.interval_id != interval_id]
            scheduled = self._prompts.schedule(state_after, events) if events else []
            active_prompts = _unique_active_prompts(memory, interval_start)
            state = TimelineState(
                timestamp=interval_start,
                story_state=state_after.model_copy(deep=True),
                prompts=_dedupe_prompts([*active_prompts, *scheduled], interval_start, interval_end),
                drawer_state=self._drawer.build(state_after, interval_start),
            )
            state.drawer_state.end_timestamp = interval_end
            memory.intervals.append(TimelineInterval(
                interval_id=interval_id,
                start_timestamp=interval_start,
                end_timestamp=interval_end,
                triggering_event_ids=[event.event_id for event in events],
                importance=max((event.importance_score for event in events), default=0.0),
                story_state_before=state_before.model_copy(deep=True),
                story_state_after=state_after.model_copy(deep=True),
                state=state,
            ))
            memory.intervals.sort(key=lambda item: item.start_timestamp)
            self._save(self._repair(memory))
        logger.info("[INTERVAL TIMELINE SNAPSHOT] movie=%s interval=%s events=%d start=%.2f end=%.2f", state_after.movie_id, interval_id, len(events), interval_start, interval_end)
        return state

    def at(self, movie_id: str, timestamp: float) -> TimelineState | None:
        with self._lock:
            return self._resolver.at(self._repair(self._load(movie_id)), timestamp)

    def get(self, movie_id: str) -> TimelineMemory:
        with self._lock:
            return self._repair(self._load(movie_id))

    def reset(self, movie_id: str) -> None:
        """Discard only the prior preprocessing timeline before a fresh run."""
        with self._lock:
            path = self._path(movie_id)
            if path.is_file():
                path.unlink()
        logger.info("[PREPROCESSING TIMELINE RESET] movie=%s", movie_id)

    def _load(self, movie_id: str) -> TimelineMemory:
        path = self._path(movie_id)
        if not path.is_file():
            return TimelineMemory(movie_id=movie_id)
        try:
            return TimelineMemory.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            # Persisted semantic memory is optional cache data. A bad legacy
            # entry must never turn playback into a 422 response.
            logger.exception("[TIMELINE REPAIR] movie=%s action=discard_invalid_cache", movie_id)
            return TimelineMemory(movie_id=movie_id)

    @staticmethod
    def _repair(memory: TimelineMemory) -> TimelineMemory:
        """Canonicalize interval/prompt lifetimes before any resolver sees them."""
        intervals = sorted(memory.intervals, key=lambda item: (item.start_timestamp, item.interval_id))
        repaired = []
        seen_intervals: set[str] = set()
        for index, interval in enumerate(intervals):
            # Fixed intervals may legitimately have no new semantic trigger.
            # Their own interval ID—not an empty event list—is the identity.
            if interval.interval_id in seen_intervals:
                continue
            seen_intervals.add(interval.interval_id)
            next_start = intervals[index + 1].start_timestamp if index + 1 < len(intervals) else None
            if next_start is not None and (interval.end_timestamp is None or interval.end_timestamp > next_start):
                interval.end_timestamp = next_start
            if interval.end_timestamp is not None and interval.end_timestamp < interval.start_timestamp:
                interval.end_timestamp = interval.start_timestamp
            interval.state.drawer_state.start_timestamp = interval.start_timestamp
            interval.state.drawer_state.end_timestamp = interval.end_timestamp
            interval.state.prompts = _dedupe_prompts(interval.state.prompts, interval.start_timestamp, interval.end_timestamp)
            repaired.append(interval)
        memory.intervals = repaired
        return memory

    def _save(self, memory: TimelineMemory) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._path(memory.movie_id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(memory.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)

    def _path(self, movie_id: str) -> Path:
        return self._root / f"{sha256(movie_id.encode('utf-8')).hexdigest()}.json"


def _dedupe_prompts(prompts, interval_start: float, interval_end: float | None):
    result = []
    seen: set[str] = set()
    for prompt in sorted(prompts, key=lambda item: (item.priority, item.start_timestamp, item.prompt_id)):
        if not prompt.prompt_id or prompt.prompt_id in seen:
            continue
        seen.add(prompt.prompt_id)
        if prompt.start_timestamp < interval_start:
            prompt.start_timestamp = interval_start
        if prompt.end_timestamp is not None and prompt.end_timestamp < prompt.start_timestamp:
            prompt.end_timestamp = prompt.start_timestamp
        # An interval boundary is never an implicit prompt expiration. Only
        # retain a prompt that can be active somewhere in this interval.
        if interval_end is not None and prompt.end_timestamp is not None and prompt.end_timestamp <= interval_start:
            continue
        result.append(prompt)
    return result


def _unique_active_prompts(memory: TimelineMemory, timestamp: float):
    prompts = [prompt for interval in memory.intervals for prompt in interval.state.prompts if prompt.start_timestamp <= timestamp and (prompt.end_timestamp is None or timestamp < prompt.end_timestamp)]
    return _dedupe_prompts(prompts, 0, None)


def _expire_prompts(memory: TimelineMemory, events: list[StoryEvent], timestamp: float) -> None:
    """Expire timeline prompts only in response to a semantic transition."""
    incoming_types = {event.event_type for event in events}
    for interval in memory.intervals:
        for prompt in interval.state.prompts:
            if prompt.end_timestamp is not None or prompt.start_timestamp >= timestamp:
                continue
            reason = None
            if prompt.activation_reason == "conflict_begins" and "conflict_resolved" in incoming_types:
                reason = "conflict_resolved"
            elif prompt.activation_reason == "goal_introduced" and "goal_completed" in incoming_types:
                reason = "goal_completed"
            elif prompt.activation_reason not in {"conflict_begins", "goal_introduced"}:
                reason = "superseded_by_semantic_change"
            if reason:
                prompt.end_timestamp = timestamp
                logger.info("[PROMPT EXPIRATION] prompt=%s timestamp=%.2f reason=%s", prompt.prompt_id, timestamp, reason)
