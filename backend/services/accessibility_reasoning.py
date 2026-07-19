"""Accessibility reasoning over the canonical StoryState only."""
from __future__ import annotations

import logging
from time import perf_counter

from models.accessibility_reasoner import AccessibilityReasoner
from schemas.interval_state import (
    AccessibilityHints, ConversationContext, IntervalMetadata, IntervalPrompts,
    IntervalCacheMetadata, IntervalSemanticMemory, IntervalState, IntervalStoryState, VisualDrawerState,
)
from schemas.accessibility_reasoning import (
    AccessibilityReasoningRequest, CharacterCard, ConversationSimplification,
    EmotionSummary, MemoryReminder, PromptBubbleSuggestion, RelationshipSummary,
    VocabularyAssistance,
)
from schemas.story_state import StoryEvent, is_user_facing_story_event
from services.story_state_presenter import StoryStatePresenter

logger = logging.getLogger(__name__)


class AccessibilityReasoningEngine(AccessibilityReasoner):
    """Derives accessibility support from StoryState; it never reads claims."""

    def __init__(self, cooldown_seconds: float | None = None):
        # Compatibility parameter retained; prompt history now belongs to StoryState.
        self._cooldown_seconds = cooldown_seconds or 0

    def reason(self, request: AccessibilityReasoningRequest, *, knowledge_revision: int = 1) -> IntervalState:
        started = perf_counter()
        state = request.story_state
        presented_state = StoryStatePresenter().present(state, request.timeline_state)
        limit = 6 if "more" in request.accessibility_profile.detail_level.lower() else 4
        timeline_prompts = _timeline_prompts(request.timeline_state)
        prompts = PromptRankingEngine().rank(state, request.accessibility_profile, limit, existing=timeline_prompts)
        cards = [CharacterCard(character_id=f"character-{index}", name=character.name, reminder="Important in the current story.", confidence=1.0, claim_ids=[]) for index, character in enumerate(presented_state.active_characters)]
        relationships = [RelationshipSummary(relationship_id=f"relationship-{index}", summary=value, confidence=1.0, claim_ids=[]) for index, value in enumerate(_clean_relationships(state))]
        # Preserve the existing timeline-card wording for API consumers.  The
        # StoryState dashboard itself receives the presenter’s compact phase.
        emotions = [EmotionSummary(emotion_id=f"emotion-{index}", summary=value, confidence=1.0, claim_ids=[]) for index, value in enumerate([presented_state.scene_mood] if presented_state.scene_mood else [])]
        reminders = [MemoryReminder(summary=value, confidence=1.0, claim_ids=[]) for value in presented_state.memory_reminders[:limit]]
        interval = request.timeline_state
        drawer = presented_state.tabs
        result = IntervalState(
            metadata=IntervalMetadata(
                interval_id=_interval_id(state, interval), catalog_scene_id=None,
                movie_id=state.movie_id, start_time=interval.timestamp if interval else state.current_timestamp,
                end_time=interval.drawer_state.end_timestamp if interval else None,
                interval_number=_interval_number(state, interval), knowledge_revision=knowledge_revision,
            ),
            prompts=IntervalPrompts(prompt_bubbles=tuple(prompts), suggested_questions=tuple(prompt.question for prompt in prompts)),
            visualDrawer=VisualDrawerState(
                story_now=tuple(drawer.story_now), relationships=tuple(drawer.relationships),
                timeline=tuple(_unique_presentation_text(item for item in (drawer.previous_event, drawer.current_event, drawer.next_event) if item)),
                emotion=drawer.emotion, cause_effect=tuple(drawer.cause_effect), objects=tuple(drawer.objects), memory=tuple(drawer.memories),
            ),
            storyState=IntervalStoryState(
                scene_summary=presented_state.scene_summary, current_goal=presented_state.current_goal,
                current_interval_id=state.current_interval_id, timeline_position=presented_state.timeline_position,
                story_so_far=tuple(presented_state.story_summary), unresolved_threads=tuple(presented_state.unresolved_threads),
            ),
            characters=tuple(cards), relationships=tuple(relationships[:limit]), memory=tuple(reminders),
            conversationContext=ConversationContext(
                scene_explanation=presented_state.scene_summary or "Story context is building for this moment.",
                simplifications=tuple(_conversations(state, limit)),
            ),
            accessibilityHints=AccessibilityHints(vocabulary=(), emotions=tuple(emotions[:limit])),
            # The preprocessing pipeline replaces these placeholders with the
            # precise before/after checkpoints and cache provenance before it
            # persists an IntervalState.
            semanticMemoryBefore=_memory_checkpoint(state),
            semanticMemoryAfter=_memory_checkpoint(state),
            cacheMetadata=IntervalCacheMetadata(semantic_cache_key="pending", knowledge_source="preprocessing", semantic_map_cached=False),
        )
        logger.info("[ACCESSIBILITY REASONING] movie=%s state_events=%d prompts=%d duration_ms=%.1f", state.movie_id, len(state.story_so_far), len(prompts), (perf_counter() - started) * 1000)
        return result


def _interval_id(state, timeline_state) -> str:
    if timeline_state is not None:
        return f"{state.movie_id}:{timeline_state.timestamp:.3f}"
    return f"{state.movie_id}:{state.current_timestamp:.3f}"


def _memory_checkpoint(state):
    return IntervalSemanticMemory(
        active_characters=tuple(item.name for item in state.known_characters.values() if item.current_visibility),
        relationships=tuple(item.summary for item in state.known_relationships.values()),
        emotions=tuple(state.active_emotions.values()),
        important_objects=tuple(item.name for item in state.known_objects.values()),
        unresolved_threads=tuple(item.summary for item in state.open_story_threads if is_user_facing_story_event(item)),
        story_events=tuple(item.summary for item in state.story_so_far if is_user_facing_story_event(item)),
    )


def _interval_number(state, timeline_state) -> int:
    if timeline_state is None:
        return len(state.story_so_far)
    return len(state.story_so_far)


class PromptRankingEngine:
    """Builds and ranks prompts from one StoryState snapshot for an interval."""

    def rank(self, state, profile, limit: int, existing: list[PromptBubbleSuggestion] | None = None) -> list[PromptBubbleSuggestion]:
        candidates = list(existing or [])
        candidates.extend(self._candidates(state))
        meaningful = _has_meaningful_state(state)
        unique: dict[str, PromptBubbleSuggestion] = {}
        for candidate in candidates:
            key = f"{candidate.kind}:{candidate.question.casefold()}"
            if key in unique:
                logger.info("[PROMPT REJECTION] id=%s reason=duplicate", candidate.id)
                continue
            unique[key] = candidate
            logger.info("[PROMPT CANDIDATE] id=%s tier=%s source=%s question=%s", candidate.id, _tier(candidate.priority), candidate.semantic_event, candidate.question)
        # Persisted interval prompts represent the triggering StoryEvents, so
        # keep them visible before supporting state-derived questions.
        ranked = sorted(unique.values(), key=lambda item: (0 if item.id.startswith("timeline-prompt:") else 1, item.priority, item.id))[:min(5, max(2, limit))]
        if meaningful and len(ranked) < 2:
            for fallback in self._fallbacks(state):
                if len(ranked) >= 2:
                    break
                if all(item.question.casefold() != fallback.question.casefold() for item in ranked):
                    ranked.append(fallback)
                    logger.info("[PROMPT FALLBACK] id=%s reason=insufficient_survivors", fallback.id)
        if meaningful and not ranked:
            logger.error("[PROMPT FALLBACK] movie=%s reason=zero_candidates_with_meaningful_state", state.movie_id)
            ranked = self._fallbacks(state)[:2]
        logger.info("[PROMPT RANKING] movie=%s generated=%d rejected=%d final=%d meaningful=%s", state.movie_id, len(candidates), len(candidates) - len(unique), len(ranked), meaningful)
        return ranked

    def _candidates(self, state) -> list[PromptBubbleSuggestion]:
        timestamp = state.current_timestamp
        result: list[PromptBubbleSuggestion] = []
        for event in state.recent_events:
            if not is_user_facing_story_event(event):
                continue
            label, question, kind = _prompt_copy(event)
            priority = 1 if event.event_type in {"conflict_begins", "conflict_resolved", "relationship_changed", "emotion_changed"} else 2
            result.append(_state_prompt(f"event:{event.event_id}", kind, label, question, priority, timestamp, event.event_type))
        for character in state.known_characters.values():
            if character.current_visibility:
                result.append(_state_prompt(f"character:{character.id}", "character", f"About {character.name}", f"Who is {character.name}, and why are they important here?", 2, timestamp, "character"))
        for relationship in state.known_relationships.values():
            result.append(_state_prompt(f"relationship:{relationship.id}", "relationship", "Why does this connection matter?", f"What does this relationship mean right now?", 1, timestamp, "relationship"))
        if state.active_emotions:
            result.append(_state_prompt("emotion", "emotion", "Why did the mood change?", "Why is everyone feeling this way now?", 1, timestamp, "emotion"))
        if state.timeline_history:
            result.append(_state_prompt("timeline", "timeline", "Where are we in the story?", "What changed to bring the story to this point?", 2, timestamp, "timeline"))
        if state.known_objects:
            result.append(_state_prompt("object", "object", "Why does this matter?", "Why is this object important in this moment?", 2, timestamp, "object"))
        if len(state.story_so_far) >= 2:
            result.append(_state_prompt("cause-effect", "scene", "What caused this?", "What happened earlier to cause this moment?", 2, timestamp, "cause_effect"))
        if state.memory_reminders:
            result.append(_state_prompt("memory", "memory", "What should I remember?", "What earlier moment helps explain this scene?", 2, timestamp, "memory"))
        return result

    def _fallbacks(self, state) -> list[PromptBubbleSuggestion]:
        timestamp = state.current_timestamp
        fallbacks = [
            _state_prompt("fallback:change", "scene", "What changed?", "What changed in this scene?", 2, timestamp, "fallback"),
            _state_prompt("fallback:importance", "scene", "Why does this matter?", "Why is this moment important?", 3, timestamp, "fallback"),
        ]
        if state.known_characters:
            fallbacks.insert(0, _state_prompt("fallback:characters", "character", "Who are these characters?", "Who are these characters?", 2, timestamp, "fallback"))
        return fallbacks


def _state_prompt(source: str, kind: str, label: str, question: str, priority: int, timestamp: float, semantic_event: str) -> PromptBubbleSuggestion:
    return PromptBubbleSuggestion(
        id=f"state-prompt:{source}:{timestamp:.3f}", kind=kind, label=label,
        question=question, priority=priority, claim_ids=[], timestamp_start=timestamp,
        timestamp_end=None, semantic_event=semantic_event, screen_location="bottom-right",
    )


def _tier(priority: int) -> str:
    return {1: "critical", 2: "helpful"}.get(priority, "optional")


def _has_meaningful_state(state) -> bool:
    return bool(
        state.story_so_far or state.recent_events or state.known_characters
        or state.known_relationships or state.active_emotions or state.known_objects
        or state.timeline_history or state.memory_reminders
    )


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


def _clean_relationships(state):
    return [item.summary for item in state.known_relationships.values() if item.summary and "unknown" not in item.summary.lower()]


def _character_reminder(state, character_id):
    history = state.character_history.get(character_id, [])
    return f"Seen in {len(history)} important story moment{'s' if len(history) != 1 else ''}."


def _conversations(state, limit):
    return [ConversationSimplification(dialogue_id=event.event_id, simple_text=event.summary, confidence=event.confidence, claim_ids=[]) for event in state.recent_events if is_user_facing_story_event(event) and event.event_type in {"conversation_started", "conversation_ended"}][:limit]


def _timeline_prompts(timeline_state):
    if timeline_state is None:
        return []
    active = [item for item in timeline_state.prompts if item.activation_reason not in {"semantic_observation", "semantic_state_reused", "cache_replayed", "semantic_graph_reused"} and (item.end_timestamp is None or timeline_state.timestamp < item.end_timestamp)]
    # TimelineMemory retains all prompts. The panel receives only the best
    # five active objects for the current timestamp.
    return [PromptBubbleSuggestion(id=item.prompt_id, kind=item.kind, label=item.label, question=item.question, priority=item.priority, claim_ids=[], timestamp_start=item.start_timestamp, timestamp_end=item.end_timestamp, semantic_event=item.activation_reason, screen_location="bottom-right") for item in sorted(active, key=lambda item: (item.priority, item.start_timestamp, item.prompt_id))[:5]]


def _unique_presentation_text(values):
    """IntervalState lists must be unique even when legacy events share copy."""
    result = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
