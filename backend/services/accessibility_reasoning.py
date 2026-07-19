"""Accessibility reasoning over the canonical StoryState only."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter

from models.accessibility_reasoner import AccessibilityReasoner
from schemas.accessibility_presentation import AccessibilityPresentation
from schemas.accessibility_reasoning import (
    AccessibilityReasoningRequest, CharacterCard, ConversationSimplification,
    EmotionSummary, LiveStoryAssistant, MemoryReminder, PromptBubbleSuggestion,
    RelationshipSummary, TimelineSummary, VocabularyAssistance,
)
from schemas.story_state import StoryEvent

logger = logging.getLogger(__name__)


class AccessibilityReasoningEngine(AccessibilityReasoner):
    """Derives accessibility support from StoryState; it never reads claims."""

    def __init__(self, cooldown_seconds: float | None = None):
        # Compatibility parameter retained; prompt history now belongs to StoryState.
        self._cooldown_seconds = cooldown_seconds or 0

    def reason(self, request: AccessibilityReasoningRequest) -> AccessibilityPresentation:
        started = perf_counter()
        state = request.story_state
        limit = 6 if "more" in request.accessibility_profile.detail_level.lower() else 4
        prompts = _timeline_prompts(request.timeline_state) if request.timeline_state else PromptRankingEngine().rank(state, request.accessibility_profile, limit)
        cards = [CharacterCard(character_id=item.id, name=item.name, reminder=_character_reminder(state, item.id), confidence=1.0, claim_ids=[]) for item in state.known_characters.values()]
        relationships = [RelationshipSummary(relationship_id=key, summary=value.summary, confidence=1.0, claim_ids=value.supporting_claim_ids) for key, value in state.known_relationships.items()]
        timeline = TimelineSummary(summary=state.timeline_history[-1].summary, confidence=state.timeline_history[-1].confidence, claim_ids=state.timeline_history[-1].semantic_claim_ids) if state.timeline_history else None
        emotions = [EmotionSummary(emotion_id=key, summary=value, confidence=1.0, claim_ids=[]) for key, value in state.active_emotions.items()]
        reminders = [MemoryReminder(summary=event.summary, confidence=event.confidence, claim_ids=event.semantic_claim_ids) for event in state.memory_reminders[-limit:]]
        result = AccessibilityPresentation(
            scene_explanation=_scene_summary(state), prompt_bubbles=prompts, character_cards=cards,
            relationship_summaries=relationships[:limit], timeline_summary=timeline,
            emotion_summaries=emotions[:limit], memory_reminders=reminders,
            vocabulary_assistance=[], conversation_simplifications=_conversations(state, limit),
            live_story=_live_story(state, request.timeline_state), story_state=state,
        )
        logger.info("[ACCESSIBILITY REASONING] movie=%s state_events=%d prompts=%d duration_ms=%.1f", state.movie_id, len(state.story_so_far), len(prompts), (perf_counter() - started) * 1000)
        return result


class PromptRankingEngine:
    """Ranks every meaningful StoryEvent; it does not use a second memory."""

    def rank(self, state, profile, limit: int) -> list[PromptBubbleSuggestion]:
        candidates = []
        for event in state.recent_events:
            if not event.requires_prompt:
                logger.info("[PROMPT REJECTION] event=%s reason=not_prompt_worthy", event.event_id)
                continue
            if not event.is_new:
                logger.info("[PROMPT REJECTION] event=%s reason=not_novel", event.event_id)
                continue
            if state.prompt_history.get(event.event_id, -float("inf")) >= event.timestamp_start:
                logger.info("[PROMPT REJECTION] event=%s reason=already_presented", event.event_id)
                continue
            candidates.append(event)
        ranked = sorted(candidates, key=lambda event: self._score(event, state, profile), reverse=True)
        prompts = [self._prompt(event) for event in ranked[:min(5, limit)]]
        # A fallback is permitted only when this window contains no meaningful event.
        if not prompts and not any(event.importance_score >= 1 for event in state.recent_events):
            fallback = next(iter(state.known_characters.values()), None)
            if fallback:
                prompts = [PromptBubbleSuggestion(id=f"fallback:{fallback.id}:{state.current_timestamp}", kind="character", label=f"About {fallback.name}", question=f"Who is {fallback.name}?", priority=3, timestamp_start=state.current_timestamp, timestamp_end=state.current_timestamp, semantic_event="fallback", screen_location="bottom-right")]
        event_ids = {event.event_id for event in state.story_so_far}
        for prompt in prompts:
            if prompt.id.startswith("prompt:") and prompt.id.removeprefix("prompt:") not in event_ids:
                raise AssertionError("prompt references a missing StoryEvent")
        logger.info("[PROMPT RANKING] movie=%s generated_candidates=%d kept=%d limit=%d", state.movie_id, len(candidates), len(prompts), min(5, limit))
        return prompts

    @staticmethod
    def _score(event, state, profile) -> float:
        novelty = 1.5 if event.is_new else 0
        progression = 1.0 if event.event_type in {"timeline_changed", "scene_transition", "conflict_begins", "conflict_resolved", "goal_introduced", "goal_completed"} else 0
        cognitive_load = 0.4 if len(state.recent_events) > 5 else 0
        preference = 0.5 if any(word in " ".join(profile.preferred_prompt_types).lower() for word in event.event_type.split("_")) else 0
        return event.importance_score + novelty + progression + preference - cognitive_load

    @staticmethod
    def _prompt(event: StoryEvent) -> PromptBubbleSuggestion:
        label, question, kind = _prompt_copy(event)
        return PromptBubbleSuggestion(id=f"prompt:{event.event_id}", kind=kind, label=label, question=question, priority=max(1, 5 - int(min(event.importance_score, 4))), claim_ids=event.semantic_claim_ids, timestamp_start=event.timestamp_start, timestamp_end=event.timestamp_end, semantic_event=event.event_type, screen_location="bottom-right")


def _prompt_copy(event):
    mapping = {
        "character_introduced": ("Who is this character?", "Who is this new character, and why do they matter?", "character"),
        "emotion_changed": ("Why are they feeling this?", "What changed to cause this emotion?", "emotion"),
        "relationship_changed": ("Why does this connection matter?", "What changed in this relationship?", "relationship"),
        "conflict_begins": ("Why is this conflict important?", "What caused this conflict, and what may happen next?", "scene"),
        "conflict_resolved": ("How was this resolved?", "How does this resolve the earlier conflict?", "scene"),
        "timeline_changed": ("Where are we in the story?", "What has led to this point in the story?", "timeline"),
    }
    return mapping.get(event.event_type, ("What changed?", f"What changed here, and why does it matter? {event.summary}", "scene"))


def _scene_summary(state):
    if state.recent_events:
        return state.recent_events[-1].summary
    return "MagiFab is building the story context for this moment."


def _character_reminder(state, character_id):
    history = state.character_history.get(character_id, [])
    return f"Seen in {len(history)} important story moment{'s' if len(history) != 1 else ''}."


def _conversations(state, limit):
    return [ConversationSimplification(dialogue_id=event.event_id, simple_text=event.summary, confidence=event.confidence, claim_ids=event.semantic_claim_ids) for event in state.recent_events if event.event_type in {"conversation_started", "conversation_ended"}][:limit]


def _timeline_prompts(timeline_state):
    if timeline_state is None:
        return []
    active = [item for item in timeline_state.prompts if item.end_timestamp is None or timeline_state.timestamp < item.end_timestamp]
    # TimelineMemory retains all prompts. The panel receives only the best
    # five active objects for the current timestamp.
    return [PromptBubbleSuggestion(id=item.prompt_id, kind=item.kind, label=item.label, question=item.question, priority=item.priority, claim_ids=item.claim_ids, timestamp_start=item.start_timestamp, timestamp_end=item.end_timestamp, semantic_event=item.activation_reason, screen_location="bottom-right") for item in sorted(active, key=lambda item: (item.priority, item.start_timestamp, item.prompt_id))[:5]]


def _live_story(state, timeline_state=None):
    drawer = timeline_state.drawer_state if timeline_state else None
    return LiveStoryAssistant(
        current_scene=state.current_scene or "Unknown scene", current_timestamp=state.current_timestamp, current_goal=state.current_goal,
        current_characters=drawer.current_characters if drawer else [item.name for item in state.known_characters.values()],
        current_emotions=drawer.current_emotions if drawer else list(state.active_emotions.values()), current_relationships=drawer.current_relationships if drawer else [item.summary for item in state.known_relationships.values()],
        recent_events=[event.summary for event in state.recent_events],
        timeline_position=state.timeline_history[-1].summary if state.timeline_history else None,
        story_so_far=drawer.story_so_far if drawer else [event.summary for event in state.story_so_far[-12:]],
        important_objects=drawer.current_objects if drawer else [item.name for item in state.known_objects.values()],
        memory_reminders=drawer.important_memories if drawer else [event.summary for event in state.memory_reminders[-6:]],
        unresolved_story_threads=drawer.unresolved_questions if drawer else [event.summary for event in state.open_story_threads],
    )
