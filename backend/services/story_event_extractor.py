"""Converts transient semantic claims into canonical story events."""
from __future__ import annotations

import logging

from schemas.reasoning_context import ReasoningContext
from schemas.story_state import StoryEntity, StoryEvent, StoryState

logger = logging.getLogger(__name__)


class StoryEventExtractor:
    """This is the sole bridge from semantic graph facts to story progression."""

    def extract(self, context: ReasoningContext, previous: StoryState, *, window_start: float | None = None, window_end: float | None = None) -> list[StoryEvent]:
        characters = {entity.id: StoryEntity(id=entity.id, name=entity.name, entity_type="character") for entity in context.active_characters}
        objects = {entity.id: StoryEntity(id=entity.id, name=entity.name, entity_type="object") for entity in context.active_objects}
        events: list[StoryEvent] = []
        # Perception windows may be supplied for diagnostics only. Semantic
        # events use the claim/playback timestamp, never a fixed window range.
        interval_start = context.timestamp_seconds
        interval_end = context.timestamp_seconds
        character_claims = {entity.id: entity.claim_ids for entity in context.active_characters}
        object_claims = {entity.id: entity.claim_ids for entity in context.active_objects}
        for character in characters.values():
            if character.id not in previous.known_characters:
                events.append(self._event("character_introduced", context, character_claims[character.id], [character], f"{character.name} is introduced", 2.5, True, True, start=interval_start, end=interval_end))
        for obj in objects.values():
            if obj.id not in previous.known_objects:
                events.append(self._event("object_becomes_important", context, object_claims[obj.id], [obj], f"{obj.name} becomes important", 1.5, True, True, start=interval_start, end=interval_end))
        # A missing detector/catalog match is never proof that a character
        # left. State carries forward until explicit leave evidence exists.
        for claim in context.semantic_scene:
            kind = _event_type(claim.kind, claim.predicate, claim.value)
            if kind is None:
                continue
            entities = _entities_for_claim(claim, characters, objects)
            if kind == "relationship_changed" and not entities:
                entities = list(characters.values())[:2]
            summary = claim.value or claim.predicate.replace("_", " ")
            importance = _importance(kind, claim)
            requires_prompt = kind in {"character_introduced", "emotion_changed", "relationship_changed", "conflict_begins", "conflict_resolved", "goal_introduced", "goal_completed", "cause", "effect", "scene_transition", "timeline_changed"}
            # Repeated claims are evidence for existing state, not a new
            # story transition. Only a semantic change writes an interval.
            if any(claim.id in event.semantic_claim_ids for event in previous.story_so_far):
                continue
            if kind == "location_changed" and previous.current_location == summary:
                continue
            events.append(self._event(kind, context, [claim.id], entities, summary, importance, True, requires_prompt, claim.confidence, context.timestamp_seconds, context.timestamp_seconds))
        # Stable identity keeps replaying a prepared window idempotent.
        result = list({event.event_id: event for event in events}.values())
        known_ids = {event.event_id for event in previous.story_so_far}
        result = [event.model_copy(update={"is_new": event.event_id not in known_ids}) for event in result]
        if context.semantic_scene and not result:
            # Reused semantic evidence is useful operational telemetry, but it
            # is not a story event and must never enter StoryState, timeline
            # memory, or an IntervalState presentation list.
            logger.info("[SEMANTIC STATE REUSED] movie=%s scene=%s timestamp=%.2f", context.movie_id, context.scene_id, context.timestamp_seconds)
        logger.info("[STORY EVENT] movie=%s scene=%s extracted=%d new=%d", context.movie_id, context.scene_id, len(result), sum(event.is_new for event in result))
        return result

    @staticmethod
    def _event(event_type, context, claim_ids, entities, summary, importance, is_new, requires_prompt, confidence=1.0, start=None, end=None):
        start = context.timestamp_seconds if start is None else start
        end = context.timestamp_seconds if end is None else end
        subject = claim_ids[0] if claim_ids else ":".join(entity.id for entity in entities) or context.scene_id
        return StoryEvent(
            event_id=f"{context.movie_id}:{event_type}:{subject}:{start:.3f}", timestamp_start=start, timestamp_end=end,
            importance_score=importance, confidence=confidence, event_type=event_type,
            semantic_claim_ids=claim_ids, entities=entities, summary=summary,
            is_new=is_new, requires_memory=importance >= 1.0 or event_type not in {"character_present"}, requires_prompt=requires_prompt,
        )


def _event_type(kind: str, predicate: str, value: str) -> str | None:
    text = f"{predicate} {value}".lower()
    if kind == "character_present" or kind == "object_present": return None
    if kind == "emotion": return "emotion_changed"
    if kind == "relationship": return "relationship_changed"
    if kind == "timeline_change": return "timeline_changed"
    if kind == "scene_state": return "location_changed"
    if kind == "callback": return "conversation_started" if predicate == "dialogue" else "cause"
    if kind == "event":
        if "conflict" in text and any(word in text for word in ("resolve", "ends", "stops")): return "conflict_resolved"
        if "conflict" in text or any(word in text for word in ("fight", "tease", "attack")): return "conflict_begins"
        if any(word in text for word in ("goal", "plan", "decides")): return "goal_introduced"
        if any(word in text for word in ("complete", "achieves", "succeeds")): return "goal_completed"
        return "effect" if any(word in text for word in ("because", "after", "result")) else "story_event"
    return None


def _entities_for_claim(claim, characters, objects):
    result = []
    for entity_id in (claim.subject_id, claim.object_id):
        if entity_id and entity_id in characters:
            result.append(characters[entity_id])
        elif entity_id and entity_id in objects:
            result.append(objects[entity_id])
    return list({entity.id: entity for entity in result}.values())


def _importance(event_type, claim) -> float:
    base = {"emotion_changed": 2.0, "relationship_changed": 2.5, "timeline_changed": 2.0, "conflict_begins": 3.0, "conflict_resolved": 3.0, "goal_introduced": 2.5, "goal_completed": 2.5, "cause": 2.0, "effect": 1.8, "location_changed": 1.0}.get(event_type, 1.0)
    return base + (0.5 if claim.knowledge_ids else 0.0)
