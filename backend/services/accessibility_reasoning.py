"""Accessibility reasoning over the canonical StoryState only."""
from __future__ import annotations

import logging
from time import perf_counter

from models.accessibility_reasoner import AccessibilityReasoner
from schemas.interval_state import (
    AccessibilityHints, ConversationContext, IntervalMetadata, IntervalPrompts,
    IntervalCacheMetadata, IntervalSemanticMemory, IntervalState, IntervalStoryState, IntervalTimelineMemory, VisualDrawerState,
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
        # The prompt panel is intentionally a fixed cognitive load: exactly
        # one ranked prompt for each comprehension need in every interval.
        limit = 4
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
        accessibility_card = _accessibility_card(presented_state, drawer)
        result = IntervalState(
            metadata=IntervalMetadata(
                interval_id=_interval_id(state, interval), catalog_scene_id=None,
                movie_id=state.movie_id, start_time=interval.timestamp if interval else state.current_timestamp,
                end_time=interval.drawer_state.end_timestamp if interval else None,
                interval_number=_interval_number(state, interval), knowledge_revision=knowledge_revision,
            ),
            prompts=IntervalPrompts(prompt_bubbles=tuple(prompts), suggested_questions=tuple(prompt.question for prompt in prompts)),
            visualDrawer=VisualDrawerState(
                now=accessibility_card["now"], who=accessibility_card["who"],
                important=accessibility_card["important"], remember=accessibility_card["remember"],
                why=accessibility_card["why"], next=accessibility_card["next"], word_count=accessibility_card["word_count"],
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
            timelineMemory=IntervalTimelineMemory(
                timeline_position=presented_state.timeline_position,
                previous_event=drawer.previous_event,
                current_event=drawer.current_event,
                next_event=drawer.next_event,
            ),
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


def _accessibility_card(presented_state, drawer) -> dict[str, object]:
    """Build the one compact drawer card from already-resolved story facts.

    This is intentionally presentation-only: no inference or new plot claims
    are made here.  A strict word budget keeps the whole card scannable in
    roughly ten seconds.
    """
    now = _card_text(presented_state.scene_summary, "The story continues in this moment.")
    who = _card_unique([f"{character.name}: {character.emotion or character.role}" for character in presented_state.active_characters], limit=2)
    important = _card_unique([*presented_state.important_objects, presented_state.timeline_position or ""], limit=2)
    remember = _card_unique(presented_state.memory_reminders, limit=1)
    cause = drawer.cause_effect[0] if drawer.cause_effect else None
    why = _card_text(
        f"Because {cause.cause[0].lower() + cause.cause[1:]}, {cause.effect[0].lower() + cause.effect[1:]}" if cause else drawer.current_event,
        "This moment follows the story change already described.",
    )
    next_source = drawer.next_event or (presented_state.unresolved_threads[0] if presented_state.unresolved_threads else None)
    next_item = _card_text(next_source, "Watch for the next change in the situation.")
    card: dict[str, object] = {
        "now": _short_card_text(now, 18), "who": tuple(_short_card_text(item, 12) for item in who),
        "important": tuple(_short_card_text(item, 12) for item in important),
        "remember": tuple(_short_card_text(item, 12) for item in remember),
        "why": _short_card_text(why, 18), "next": _short_card_text(next_item, 18),
    }
    _trim_card_to_budget(card, maximum_words=120)
    card["word_count"] = _card_word_count(card)
    logger.info("[DRAWER_CARD_GENERATED] now=%d who=%d important=%d remember=%d why=%d next=%d words=%d", bool(card["now"]), len(card["who"]), len(card["important"]), len(card["remember"]), bool(card["why"]), bool(card["next"]), card["word_count"])
    return card


def _card_text(value: str | None, fallback: str) -> str:
    cleaned = " ".join(value.split()) if isinstance(value, str) else ""
    return cleaned or fallback


def _short_card_text(value: str, maximum_words: int) -> str:
    words = value.split()
    return " ".join(words[:maximum_words]).rstrip(" ,;:") + ("…" if len(words) > maximum_words else "")


def _card_unique(values, *, limit: int) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(value.split()) if isinstance(value, str) else ""
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
        if len(output) == limit:
            break
    return tuple(output)


def _trim_card_to_budget(card: dict[str, object], *, maximum_words: int) -> None:
    """Keep the most useful sections intact and trim lower-priority detail."""
    for field in ("remember", "important", "who"):
        values = list(card[field])
        while len(values) > 1 and _card_word_count(card) > maximum_words:
            values.pop()
            card[field] = tuple(values)
    for field in ("next", "why", "now"):
        while _card_word_count(card) > maximum_words:
            words = str(card[field]).split()
            if len(words) <= 8:
                break
            card[field] = " ".join(words[:-1]).rstrip(" ,;:") + "…"


def _card_word_count(card: dict[str, object]) -> int:
    values = [card.get("now"), *card.get("who", ()), *card.get("important", ()), *card.get("remember", ()), card.get("why"), card.get("next")]
    return sum(len(str(value).split()) for value in values if value)


class PromptRankingEngine:
    """Produces a fixed, diverse comprehension set from one StoryState snapshot."""

    _CATEGORY_ORDER = ("critical", "memory", "emotion", "prediction")

    def rank(self, state, profile, limit: int = 4, existing: list[PromptBubbleSuggestion] | None = None) -> list[PromptBubbleSuggestion]:
        # Timeline prompts are useful audit artifacts, but they are not allowed
        # to displace one of the four interval comprehension categories.
        for prompt in existing or []:
            logger.info("[PROMPT_REJECTED] id=%s reason=outside_fixed_interval_categories", prompt.id)

        context = _PromptContext.from_state(state)
        generated = self._generate(context, profile)
        usefulness_by_id = {prompt.id: usefulness for _, usefulness, prompt in generated}
        selected: list[PromptBubbleSuggestion] = []
        seen: set[str] = set()
        for category, usefulness, prompt in generated:
            key = prompt.question.casefold()
            if key in seen or _is_generic_prompt(prompt.question):
                logger.info("[PROMPT_REJECTED] id=%s category=%s reason=%s", prompt.id, category, "duplicate" if key in seen else "generic")
                continue
            seen.add(key)
            selected.append(prompt)
            logger.info("[PROMPT_RANKED] id=%s category=%s usefulness=%d question=%s", prompt.id, category, usefulness, prompt.question)

        # The generator has one deterministic, grounded candidate per category;
        # this guards the interval API contract if that implementation changes.
        if len(selected) != 4 or {item.kind for item in selected} != set(self._CATEGORY_ORDER):
            raise ValueError("prompt_generation_did_not_produce_four_diverse_prompts")
        selected.sort(key=lambda item: (item.priority, self._CATEGORY_ORDER.index(item.kind)))
        logger.info("[PROMPT_RANKING] movie=%s generated=%d rejected=%d final=%d categories=%s", state.movie_id, len(generated), len(generated) - len(selected), len(selected), [item.kind for item in selected])
        for rank, prompt in enumerate(selected, start=1):
            logger.info("[PROMPT_SELECTED] movie=%s rank=%d id=%s category=%s usefulness=%d", state.movie_id, rank, prompt.id, prompt.kind, usefulness_by_id[prompt.id])
        return selected

    def _generate(self, context: "_PromptContext", profile) -> list[tuple[str, int, PromptBubbleSuggestion]]:
        detail = profile.detail_level.casefold()
        concise = "brief" in detail or profile.conversation_simplification
        subject = context.subject
        current = context.current
        earlier = context.earlier
        emotion = context.emotion
        next_focus = context.next_focus
        prompts = [
            ("critical", 100, _interval_prompt("critical", "Critical", f"Why is this important now: {current}?" if concise else f"Why is this important now: {current}? What does it change for {subject}?", 1, context)),
            ("memory", 90, _interval_prompt("memory", "Memory", f"Remember when {earlier}? That helps explain {current}." if concise else f"Remember when {earlier}? How does that earlier moment explain {current}?", 2, context)),
            ("emotion", 80, _interval_prompt("emotion", "Emotion", f"Why is {subject} feeling {emotion} after {current}?" if concise else f"Why is {subject} feeling {emotion} here, and which earlier change led to it?", 3, context)),
            ("prediction", 70, _interval_prompt("prediction", "Watch next", f"Watch {next_focus} carefully—it may become important next." if concise else f"Watch {next_focus} carefully. What could it change in the next part of the story?", 4, context)),
        ]
        preferred = {value.casefold() for value in profile.preferred_prompt_types}
        ranked: list[tuple[str, int, PromptBubbleSuggestion]] = []
        for category, usefulness, prompt in prompts:
            # Preferences tune order only; users still receive the whole,
            # diverse comprehension set instead of four prompts of one type.
            usefulness += 25 if category in preferred else 0
            ranked.append((category, usefulness, prompt))
        ranked.sort(key=lambda item: (-item[1], self._CATEGORY_ORDER.index(item[0])))
        ranked = [
            (category, usefulness, prompt.model_copy(update={"priority": rank}))
            for rank, (category, usefulness, prompt) in enumerate(ranked, start=1)
        ]
        for category, usefulness, prompt in ranked:
            logger.info("[PROMPT_GENERATED] id=%s category=%s usefulness=%d source=%s question=%s", prompt.id, category, usefulness, prompt.semantic_event, prompt.question)
        return ranked


class _PromptContext:
    """Small, display-safe narrative facts used by all four prompt categories."""

    def __init__(self, *, timestamp: float, current: str, earlier: str, subject: str, emotion: str, next_focus: str, source: str):
        self.timestamp = timestamp
        self.current = current
        self.earlier = earlier
        self.subject = subject
        self.emotion = emotion
        self.next_focus = next_focus
        self.source = source

    @classmethod
    def from_state(cls, state) -> "_PromptContext":
        events = [item for item in state.story_so_far if is_user_facing_story_event(item)]
        recent = [item for item in state.recent_events if is_user_facing_story_event(item)]
        current_event = recent[-1] if recent else (events[-1] if events else None)
        earlier_event = next((item for item in reversed(events) if not current_event or item.event_id != current_event.event_id), None)
        characters = [item.name for item in state.known_characters.values() if item.current_visibility]
        subject = characters[0] if characters else "the character in this moment"
        current = _prompt_fact(current_event.summary if current_event else state.current_goal, "the story is setting up a new situation")
        earlier = _prompt_fact(
            (state.memory_reminders[-1].summary if state.memory_reminders else None)
            or (earlier_event.summary if earlier_event else None),
            current,
        )
        emotion = _prompt_fact(next(iter(state.active_emotions.values()), None), "alert")
        next_focus = _prompt_fact(
            (state.open_story_threads[-1].summary if state.open_story_threads else None)
            or (current_event.summary if current_event else None)
            or (next(iter(state.known_objects.values())).name if state.known_objects else None),
            subject,
        )
        return cls(
            timestamp=state.current_timestamp, current=current, earlier=earlier,
            subject=subject, emotion=emotion, next_focus=next_focus,
            source=current_event.event_type if current_event else "story_state",
        )


def _prompt_fact(value: str | None, fallback: str) -> str:
    """Keep prompts grounded in a readable fact and never expose placeholders."""
    cleaned = " ".join(value.split()) if isinstance(value, str) else ""
    return cleaned.rstrip(".?!") if cleaned else fallback


def _interval_prompt(category: str, label: str, question: str, priority: int, context: _PromptContext) -> PromptBubbleSuggestion:
    return PromptBubbleSuggestion(
        id=f"interval-prompt:{category}:{context.timestamp:.3f}", kind=category, label=label,
        question=question, priority=priority, claim_ids=[], timestamp_start=context.timestamp,
        timestamp_end=None, semantic_event=context.source, screen_location="bottom-right",
    )


def _is_generic_prompt(question: str) -> bool:
    normalized = " ".join(question.casefold().replace("?", "").split())
    banned = {
        "who is this", "what happened", "what is this", "what changed",
        "why does this matter", "what should i remember",
    }
    return normalized in banned


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
