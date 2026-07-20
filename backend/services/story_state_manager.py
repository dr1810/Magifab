"""Preprocessing-only builder for cumulative narrative context.

This module is deliberately not part of the playback runtime.  It advances a
temporary chronological story view while IntervalStates are generated; the
immutable IntervalStateRepository owns all runtime retrieval.
"""
from __future__ import annotations

from hashlib import sha256
import logging
from pathlib import Path
from threading import Lock

from schemas.story_state import CharacterState, RelationshipState, StoryEntity, StoryEvent, StoryState, StoryStateUpdate

logger = logging.getLogger(__name__)


class PreprocessingStoryBuilder:
    """Build cumulative StoryState in preprocessing order only.

    This is not a playback state manager.  It is reset at the beginning of a
    preprocessing run and is never consulted by seek, rewind, or prompt
    response paths.
    """

    def __init__(self, root: Path, semantic_cache_version: int):
        self._root = root / f"v{semantic_cache_version}" / "story-states"
        self._lock = Lock()

    def advance(self, movie_id: str, interval_id: str, timestamp: float, events: list[StoryEvent]) -> StoryStateUpdate:
        with self._lock:
            state = self._load(movie_id)
            self._assert_transition(state, interval_id, timestamp, events)
            existing_event_ids = {event.event_id for event in state.story_so_far}
            self._advance_character_lifetimes(state, timestamp)
            state.current_interval_id = interval_id
            state.current_timestamp = timestamp
            known = {event.event_id for event in state.story_so_far}
            for event in events:
                self._apply(state, event, event.event_id not in known)
            state.recent_events = [event for event in events if event.event_id not in existing_event_ids][-8:]
            self._save(state)
        logger.info("[PREPROCESSING STORY ADVANCE] movie=%s interval=%s events=%d total=%d timestamp=%.2f", movie_id, interval_id, len(events), len(state.story_so_far), timestamp)
        return StoryStateUpdate(state=state, events=events)

    def get(self, movie_id: str) -> StoryState:
        with self._lock:
            return self._load(movie_id)

    def reset(self, movie_id: str) -> StoryState:
        """Start a fresh chronological preprocessing pass for one movie."""
        with self._lock:
            path = self._path(movie_id)
            if path.is_file():
                path.unlink()
            state = StoryState(movie_id=movie_id)
            self._save(state)
        logger.info("[PREPROCESSING STORY RESET] movie=%s schema_deserialization=no", movie_id)
        return state

    def _apply(self, state: StoryState, event: StoryEvent, is_new: bool) -> None:
        if is_new:
            state.story_so_far.append(event)
        for entity in event.entities:
            if entity.entity_type == "character":
                character = state.known_characters.get(entity.id)
                visible_duration = 0 if event.event_type == "character_left" else max(0, event.timestamp_end - event.timestamp_start)
                if character is None:
                    character = CharacterState(id=entity.id, name=entity.name, first_seen_timestamp=event.timestamp_start, last_seen_timestamp=event.timestamp_end, total_screen_time=visible_duration, current_visibility=event.event_type != "character_left", associated_events=[event.event_id])
                    state.known_characters[entity.id] = character
                else:
                    character.last_seen_timestamp = max(character.last_seen_timestamp, event.timestamp_end)
                    character.current_visibility = event.event_type != "character_left"
                    if event.event_id not in character.associated_events:
                        character.associated_events.append(event.event_id)
                        character.total_screen_time += visible_duration
                state.character_history.setdefault(entity.id, [])
                if is_new: state.character_history[entity.id].append(event)
                logger.info("[CHARACTER LIFECYCLE] character=%s visible=%s first=%.2f last=%.2f screen_time=%.2f", entity.id, character.current_visibility, character.first_seen_timestamp, character.last_seen_timestamp, character.total_screen_time)
            elif entity.entity_type == "object":
                state.known_objects[entity.id] = entity
        if event.event_type == "relationship_changed":
            if not event.semantic_claim_ids:
                raise AssertionError("relationship events require supporting semantic claims")
            key = ":".join(entity.id for entity in event.entities) or event.event_id
            if not event.entities:
                raise AssertionError("relationship events require related entities")
            relationship = state.known_relationships.get(key)
            if relationship is None:
                relationship = RelationshipState(id=key, summary=event.summary, supporting_claim_ids=event.semantic_claim_ids, first_seen_timestamp=event.timestamp_start, last_seen_timestamp=event.timestamp_end, associated_events=[event.event_id])
                state.known_relationships[key] = relationship
            else:
                relationship.summary = event.summary
                relationship.last_seen_timestamp = max(relationship.last_seen_timestamp, event.timestamp_end)
                relationship.supporting_claim_ids = list(dict.fromkeys([*relationship.supporting_claim_ids, *event.semantic_claim_ids]))
                if event.event_id not in relationship.associated_events: relationship.associated_events.append(event.event_id)
            state.relationship_history.setdefault(key, [])
            if is_new: state.relationship_history[key].append(event)
            for entity in event.entities:
                if entity.id in state.known_characters:
                    state.known_characters[entity.id].relationships = list(dict.fromkeys([*state.known_characters[entity.id].relationships, key]))
            logger.info("[RELATIONSHIP LIFECYCLE] relationship=%s claims=%d events=%d", key, len(relationship.supporting_claim_ids), len(relationship.associated_events))
        if event.event_type == "location_changed":
            state.current_location = event.summary
            state.known_locations[event.event_id] = StoryEntity(id=event.event_id, name=event.summary, entity_type="location")
        if event.event_type == "emotion_changed":
            for entity in event.entities:
                state.active_emotions[entity.id] = event.summary
        if event.event_type in {"timeline_changed", "scene_transition"} and is_new:
            state.timeline_history.append(event)
            logger.info("[TIMELINE UPDATE] movie=%s event=%s timestamp=%.2f", state.movie_id, event.event_id, event.timestamp_start)
        if event.event_type == "goal_introduced": state.current_goal = event.summary
        if event.event_type == "goal_completed": state.current_goal = None
        if event.event_type in {"conflict_begins", "goal_introduced", "cause"} and is_new:
            state.open_story_threads.append(event)
        if event.event_type in {"conflict_resolved", "goal_completed"} and is_new:
            state.resolved_threads.append(event)
            state.open_story_threads = [thread for thread in state.open_story_threads if thread.event_type not in {"conflict_begins", "goal_introduced"}]
        if event.importance_score >= 2 and is_new:
            state.memory_reminders.append(event)
            state.memory_reminders = state.memory_reminders[-12:]

    @staticmethod
    def _assert_transition(state: StoryState, interval_id: str, timestamp: float, events: list[StoryEvent]) -> None:
        # Chronological order belongs exclusively to the preprocessing writer.
        # Playback never calls this builder; it retrieves immutable snapshots.
        if timestamp < state.current_timestamp:
            raise AssertionError("preprocessing intervals must be generated in chronological order")
        event_ids = [event.event_id for event in events]
        if len(event_ids) != len(set(event_ids)):
            raise AssertionError("duplicate StoryEvent IDs in one sliding window")
        existing_ids = {event.event_id for event in state.story_so_far}
        for event in events:
            if event.timestamp_start > event.timestamp_end:
                raise AssertionError("StoryEvent has an invalid timestamp interval")
            if not event.timestamp_start <= timestamp <= event.timestamp_end:
                raise AssertionError("StoryEvent timestamp is not synchronized with movie playback")
            if event.event_id in existing_ids and event.is_new:
                raise AssertionError("existing StoryEvent cannot be marked new")
            if event.event_id not in existing_ids and not event.is_new:
                raise AssertionError("new StoryEvent must be marked new")
        timeline_ids = [event.event_id for event in state.timeline_history]
        if len(timeline_ids) != len(set(timeline_ids)):
            raise AssertionError("duplicate timeline entries")

    @staticmethod
    def _advance_character_lifetimes(state: StoryState, timestamp: float) -> None:
        """Account for continuous visibility only at semantic change points."""
        elapsed = timestamp - state.current_timestamp
        if elapsed <= 0:
            return
        for character in state.known_characters.values():
            if character.current_visibility:
                character.total_screen_time += elapsed
                character.last_seen_timestamp = timestamp

    def _load(self, movie_id: str) -> StoryState:
        path = self._path(movie_id)
        if not path.is_file():
            return StoryState(movie_id=movie_id)
        try:
            return StoryState.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            logger.exception("[STORY STATE] movie=%s action=discard_invalid_cache", movie_id)
            return StoryState(movie_id=movie_id)

    def _save(self, state: StoryState) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._path(state.movie_id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)

    def _path(self, movie_id: str) -> Path:
        return self._root / f"{sha256(movie_id.encode('utf-8')).hexdigest()}.json"
