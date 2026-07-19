"""Resolves the one semantic timeline snapshot valid at a playback timestamp."""
from schemas.timeline_memory import TimelineMemory, TimelineState


class SemanticStateResolver:
    def at(self, memory: TimelineMemory, timestamp: float) -> TimelineState | None:
        active = [item for item in memory.intervals if item.start_timestamp <= timestamp and (item.end_timestamp is None or timestamp < item.end_timestamp)]
        if active:
            return self._at_timestamp(max(active, key=lambda item: item.start_timestamp).state, timestamp)
        earlier = [item for item in memory.intervals if item.start_timestamp <= timestamp]
        return self._at_timestamp(max(earlier, key=lambda item: item.start_timestamp).state, timestamp) if earlier else None

    @staticmethod
    def _at_timestamp(state: TimelineState, timestamp: float) -> TimelineState:
        # Playback time is presentation state, not a semantic mutation.
        return state.model_copy(update={"timestamp": timestamp, "story_state": state.story_state.model_copy(update={"current_timestamp": timestamp})})
