"""Sliding-window temporal memory for semantic movie understanding.

This service is intentionally downstream of semantic graph construction.  It
never sees pixels or captions, so temporal reasoning cannot reintroduce raw
vision descriptions into accessibility output.
"""
from __future__ import annotations

import logging
from threading import Lock

from schemas.reasoning_context import ReasoningContext
from schemas.temporal_memory import (
    AttentionEvent, CapturedFrame, LongTermMemory, ShortTermMemory,
    SlidingWindow, TemporalMemoryUpdate,
)

logger = logging.getLogger(__name__)

_STATIC_DETAIL_WORDS = {"sky", "grass", "lighting", "light", "background", "weather", "color", "colour", "scenery"}


class SlidingWindowMemoryManager:
    """Builds bounded perception windows and attention signals.

    It retains only the short comparison state necessary to score a change.
    ``PreprocessingStoryBuilder`` owns cumulative preprocessing knowledge. Replaying the same
    prepared window is idempotent, which lets /prepare and /respond share it.
    """

    def __init__(self, window_seconds: float = 10.0, attention_threshold: float = 2.0):
        self._window_seconds = window_seconds
        self._attention_threshold = attention_threshold
        self._states: dict[str, tuple[ShortTermMemory, TemporalMemoryUpdate]] = {}
        self._lock = Lock()

    def update(self, context: ReasoningContext, *, frame_hash: str | None = None) -> TemporalMemoryUpdate:
        window = self._window_from_context(context, frame_hash)
        with self._lock:
            previous_short, previous_update = self._states.get(
                context.movie_id, (ShortTermMemory(), None)
            )
            comparison_window = previous_short.current_window
            if previous_update and _same_window(previous_update.window, window):
                # /respond commonly follows /prepare for exactly the same
                # semantic frame.  Do not manufacture a second recurrence.
                if _is_replay(previous_update.window, window):
                    return previous_update
                # Several sampled frames can belong to one ten-second window.
                # Fold them into its frame list and semantic aggregate.
                window = _merge_windows(previous_update.window, window)

            # A seek backwards begins a fresh short-term sequence. Long-term
            # knowledge remains available, like an LSTM's durable companion memory.
            if previous_short.current_window and window.start_timestamp < previous_short.current_window.start_timestamp:
                previous_short = ShortTermMemory()

            known_before = set(comparison_window.detected_characters) if comparison_window else set()
            new_characters = [name for name in window.detected_characters if name not in known_before]
            previous_events = set(comparison_window.events) if comparison_window else set()
            new_events = [event for event in window.events if event not in previous_events]
            attention = self._score_attention(context, window, comparison_window, new_characters, new_events)
            selected = [event.claim_id for event in attention if event.importance_score >= self._attention_threshold]

            short = ShortTermMemory(
                current_window=window,
                recent_actions=_tail(_merge(previous_short.recent_actions, window.actions), 8),
                conversation_context=_tail(_merge(previous_short.conversation_context, _conversation(context)), 8),
            )
            update = TemporalMemoryUpdate(
                # Kept empty for the private compatibility DTO. Durable state
                # belongs exclusively to PreprocessingStoryBuilder.
                window=window, short_term=short, long_term=LongTermMemory(),
                new_characters=new_characters, new_events=new_events,
                attention_events=attention, selected_claim_ids=selected,
            )
            self._states[context.movie_id] = (short, update)

        logger.info("[WINDOW] timestamp=%s-%s characters_detected=%d", _fmt(window.start_timestamp), _fmt(window.end_timestamp), len(window.detected_characters))
        logger.info("[MEMORY UPDATE] new_characters=%d new_events=%d", len(new_characters), len(new_events))
        logger.info("[ATTENTION] candidate_events=%d selected_events=%d", len(attention), len(selected))
        return update

    def _window_from_context(self, context: ReasoningContext, frame_hash: str | None) -> SlidingWindow:
        start = (context.timestamp_seconds // self._window_seconds) * self._window_seconds
        end = start + self._window_seconds
        claims = context.semantic_scene
        return SlidingWindow(
            start_timestamp=start, end_timestamp=end,
            captured_frames=[CapturedFrame(timestamp_seconds=context.timestamp_seconds, frame_hash=frame_hash)],
            detected_characters=[entity.name for entity in context.active_characters],
            detected_objects=[entity.name for entity in context.active_objects if _important(entity.name)],
            actions=[_description(claim) for claim in claims if claim.kind == "event" and _is_action(claim)],
            events=[_description(claim) for claim in claims if claim.kind in {"event", "timeline_change"} and _important(_description(claim))],
            emotions=[_description(claim) for claim in context.emotion_claims if _important(_description(claim))],
            relationships=[item.description for item in context.relationships],
            claim_ids=[claim.id for claim in claims if claim.kind != "scene_state" and _important(_description(claim))],
        )

    def _score_attention(self, context, window, previous: SlidingWindow | None, new_characters, new_events) -> list[AttentionEvent]:
        result: list[AttentionEvent] = []
        old_relationships = set(previous.relationships) if previous else set()
        old_emotions = set(previous.emotions) if previous else set()
        for claim in context.semantic_scene:
            text = _description(claim)
            if claim.kind == "scene_state" or not _important(text):
                continue
            character_change = 2.0 if claim.kind == "character_present" and any(name in text for name in new_characters) else 0.0
            relationship_change = 2.0 if claim.kind == "relationship" and text not in old_relationships else 0.0
            plot_relevance = 2.0 if claim.kind in {"event", "timeline_change"} and text in new_events else 0.0
            emotional_change = 1.5 if claim.kind == "emotion" and text not in old_emotions else 0.0
            score = character_change + relationship_change + plot_relevance + emotional_change
            if score:
                result.append(AttentionEvent(
                    claim_id=claim.id, importance_score=score,
                    character_change=character_change, relationship_change=relationship_change,
                    plot_relevance=plot_relevance, emotional_change=emotional_change,
                ))
        return result


def _description(claim) -> str:
    return claim.value.strip() or " ".join(part for part in [claim.subject_id, claim.predicate, claim.object_id] if part)


def _important(value: str) -> bool:
    words = set(value.lower().replace("_", " ").split())
    return not bool(words & _STATIC_DETAIL_WORDS)


def _is_action(claim) -> bool:
    return claim.predicate.lower() not in {"occurs", "happens", "changes"}


def _conversation(context) -> list[str]:
    return [claim.value for claim in context.conversation_claims if claim.value]


def _timeline(context) -> list[str]:
    return [context.timeline.description] if context.timeline else []


def _merge(existing: list[str], additions: list[str]) -> list[str]:
    return list(dict.fromkeys([*existing, *additions]))


def _tail(values: list[str], limit: int) -> list[str]:
    return values[-limit:]


def _same_window(left: SlidingWindow, right: SlidingWindow) -> bool:
    return left.start_timestamp == right.start_timestamp and left.end_timestamp == right.end_timestamp


def _is_replay(existing: SlidingWindow, incoming: SlidingWindow) -> bool:
    return (
        existing.claim_ids == incoming.claim_ids
        and any(frame.timestamp_seconds == incoming.captured_frames[0].timestamp_seconds for frame in existing.captured_frames)
    )


def _merge_windows(existing: SlidingWindow, incoming: SlidingWindow) -> SlidingWindow:
    return SlidingWindow(
        start_timestamp=existing.start_timestamp,
        end_timestamp=existing.end_timestamp,
        captured_frames=[*existing.captured_frames, *[
            frame for frame in incoming.captured_frames
            if not any(old.timestamp_seconds == frame.timestamp_seconds and old.frame_hash == frame.frame_hash for old in existing.captured_frames)
        ]],
        detected_characters=_merge(existing.detected_characters, incoming.detected_characters),
        detected_objects=_merge(existing.detected_objects, incoming.detected_objects),
        actions=_merge(existing.actions, incoming.actions),
        events=_merge(existing.events, incoming.events),
        emotions=_merge(existing.emotions, incoming.emotions),
        relationships=_merge(existing.relationships, incoming.relationships),
        claim_ids=_merge(existing.claim_ids, incoming.claim_ids),
    )


def _fmt(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)
