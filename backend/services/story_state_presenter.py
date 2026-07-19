"""Frontend boundary: transform internal timeline state into human story language."""
from __future__ import annotations

import logging
import re

from schemas.presented_story_state import PresentedCauseEffect, PresentedCharacter, PresentedStoryState, PresentedStoryTabs
from schemas.story_state import StoryState, is_user_facing_story_event, is_user_facing_story_text
from schemas.timeline_memory import TimelineState

logger = logging.getLogger(__name__)

_PLACEHOLDER = re.compile(r"\b(appears in|person|unknown|object|footwear|object placeholder|no story-relevant entity confirmed|observation|claim[-_ ]|debug)\b", re.I)


class StoryStatePresenter:
    """The only backend component allowed to expose StoryState to the UI.

    It intentionally accepts resolved state, not SemanticClaim objects, so the
    frontend boundary cannot regress into graph/perception leakage.
    """

    def present(self, state: StoryState, timeline: TimelineState | None = None) -> PresentedStoryState:
        drawer = timeline.drawer_state if timeline else None
        story_events = [event for event in state.story_so_far if is_user_facing_story_event(event)]
        recent_events = [event for event in state.recent_events if is_user_facing_story_event(event)]
        raw_events = [event.summary for event in story_events]
        candidates = drawer.story_so_far if drawer else raw_events
        story_summary = _clean_unique(candidates, limit=5)
        reminders = _clean_unique(drawer.important_memories if drawer else [event.summary for event in state.memory_reminders if is_user_facing_story_event(event)], limit=2)
        threads = _clean_unique(drawer.unresolved_questions if drawer else [event.summary for event in state.open_story_threads if is_user_facing_story_event(event)], limit=3)
        character_names = _clean_unique(
            drawer.current_characters if drawer else [item.name for item in state.known_characters.values() if item.current_visibility],
            limit=12,
        )
        objects = _clean_unique(drawer.current_objects if drawer else [item.name for item in state.known_objects.values()], limit=6)
        timeline_position = _timeline_position(state)
        scene_summary = _first_clean([recent_events[-1].summary] if recent_events else story_summary)
        goal = _goal(state, recent_events, story_summary, threads, timeline_position)
        tabs = _tabs(state, story_events, recent_events, scene_summary, goal, objects)
        result = PresentedStoryState(
            timestamp=timeline.timestamp if timeline else state.current_timestamp,
            # Playback chapters are intervals, not catalog scene numbers.
            scene_number=None, scene_summary=scene_summary,
            current_goal=goal, timeline_position=timeline_position,
            active_characters=_characters(state, character_names), scene_mood=_scene_mood(state),
            important_objects=objects, story_summary=story_summary,
            memory_reminders=reminders, unresolved_threads=threads, tabs=tabs,
        )
        removed = len(raw_events) - len(_clean_unique(raw_events, limit=100))
        logger.info("[STORY STATE PRESENTER] raw_events=%d normalized_events=%d removed_duplicates=%d removed_placeholders=%d final=%s", len(raw_events), len(story_summary), removed, len(raw_events) - len([item for item in raw_events if _clean(item)]), result.model_dump(mode="json"))
        return result


def _clean_unique(values, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean(value)
        if not cleaned or cleaned.casefold() in seen:
            continue
        seen.add(cleaned.casefold())
        result.append(cleaned)
        if len(result) == limit:
            break
    return result


def _first_clean(values) -> str | None:
    cleaned = _clean_unique(values, 1)
    return cleaned[0] if cleaned else None


def _clean(value) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.replace("_", " ").split())
    if not text or _PLACEHOLDER.search(text) or not is_user_facing_story_text(text):
        return None
    return text[0].upper() + text[1:]


def _goal(state, recent_events, story_summary, threads, timeline_position) -> str:
    explicit = _clean(state.current_goal)
    if explicit:
        return explicit
    if threads:
        return f"Understand how the current situation develops: {threads[0]}"
    if any(event.event_type == "conflict_begins" for event in recent_events):
        return "Understand the current conflict and what changes next."
    if timeline_position:
        return f"Follow the next important change in the story: {timeline_position}"
    if story_summary:
        return f"Follow the scene as it develops: {story_summary[-1]}"
    return "Follow the story as the scene develops."


def _scene_number(scene_id: str | None) -> int | None:
    """Expose only the readable ordinal, never an internal scene identifier."""
    if not scene_id:
        return None
    match = re.search(r"(?:scene[-_ ]*)?(\d+)$", scene_id, re.I)
    return int(match.group(1)) if match else None


def _characters(state: StoryState, names: list[str]) -> list[PresentedCharacter]:
    known_by_name = {item.name.casefold(): item for item in state.known_characters.values()}
    event_counts = {key: len(state.character_history.get(key, [])) for key in state.known_characters}
    leading_id = max(event_counts, key=event_counts.get, default=None)
    result: list[PresentedCharacter] = []
    for name in names:
        character = known_by_name.get(name.casefold())
        if character and character.id == leading_id and event_counts.get(character.id, 0):
            role = "Main character"
        elif character and character.first_seen_timestamp == state.current_timestamp:
            role = "New character"
        else:
            role = "Important character"
        emotion = _clean(state.active_emotions.get(character.id)) if character else None
        result.append(PresentedCharacter(name=name, role=role, emotion=emotion))
    return result


def _timeline_position(state: StoryState) -> str | None:
    timeline_events = [event for event in state.timeline_history if is_user_facing_story_event(event)]
    source = _first_clean([timeline_events[-1].summary] if timeline_events else [])
    if not source:
        return None
    text = source.casefold()
    if any(word in text for word in ("resolve", "resolution", "ends", "reunite", "safe")):
        return "Resolution"
    if any(word in text for word in ("conflict", "fight", "danger", "escape", "confront")):
        return "Conflict"
    if any(word in text for word in ("meet", "appear", "introduc", "discover", "finds")):
        return "First Encounter"
    if any(word in text for word in ("explor", "enter", "journey", "travel", "forest")):
        return "Exploration"
    if len(state.story_so_far) <= 1:
        return "Beginning"
    return "Story develops"


def _scene_mood(state: StoryState) -> str | None:
    emotions = _clean_unique(state.active_emotions.values(), limit=1)
    if emotions:
        emotion = emotions[0].casefold()
        if any(word in emotion for word in ("fear", "anger", "worry", "tense", "anxious")):
            return "Tense"
        if any(word in emotion for word in ("curious", "surprise", "wonder")):
            return "Curious"
        if any(word in emotion for word in ("hope", "joy", "happy")):
            return "Hopeful"
        if any(word in emotion for word in ("calm", "peace", "quiet")):
            return "Peaceful"
        return emotions[0]
    recent_events = [event for event in state.recent_events if is_user_facing_story_event(event)]
    if any(event.event_type in {"conflict_begins", "relationship_changes"} for event in recent_events):
        return "Tense"
    if any(event.event_type in {"character_introduced", "object_becomes_important", "location_changes"} for event in recent_events):
        return "Curious"
    return None


def _tabs(state: StoryState, story_events, recent_events, scene_summary: str | None, goal: str, objects: list[str]) -> PresentedStoryTabs:
    """Compose each fixed UI tab solely from resolved StoryState events.

    StoryEvent claim ids are used only for traceability in logs below; they
    are never copied into the frontend contract or used as graph content.
    """
    current = recent_events[-1] if recent_events else (story_events[-1] if story_events else None)
    previous = next((event for event in reversed(story_events) if (not current or event.event_id != current.event_id) and _clean(event.summary)), None)
    active_names = _clean_unique([item.name for item in state.known_characters.values() if item.current_visibility], limit=4)
    subject = ", ".join(active_names) if active_names else "The group"
    current_text = _clean(current.summary) if current else scene_summary
    story_now = _clean_unique(
        [current_text, f"{subject} are focused on what happens next.", f"Their current goal is to {goal[0].lower() + goal[1:]}"] if current_text else [],
        limit=4,
    )
    relationships = _clean_unique([item.summary for item in state.known_relationships.values()], limit=4)
    if not relationships and current_text:
        relationships = [f"{subject} are sharing this moment together."]
    mood = _scene_mood(state)
    emotion = None
    if mood and current_text:
        emotion = f"{subject} feel {mood.lower()} because {current_text[0].lower() + current_text[1:]}"
    elif current_text:
        emotion = f"{subject} are reacting to {current_text[0].lower() + current_text[1:]}"
    causes: list[PresentedCauseEffect] = []
    if previous and current_text:
        cause = _clean(previous.summary)
        if cause and cause.casefold() != current_text.casefold():
            causes.append(PresentedCauseEffect(cause=cause, effect=current_text))
    elif current_text:
        # First beats still need a simple causal explanation even when no
        # earlier stored beat exists in the movie memory.
        causes.append(PresentedCauseEffect(cause="The story reaches this moment.", effect=current_text))
    object_explanations: list[str] = []
    for name in objects:
        explanation = current_text if current_text and name.casefold() in current_text.casefold() else None
        object_explanations.append(f"{name} matters because {explanation[0].lower() + explanation[1:]}" if explanation else f"{name} is important in the current moment.")
    if not object_explanations and current_text:
        object_explanations = ["The characters' actions matter most in this moment."]
    memories = _clean_unique([event.summary for event in state.memory_reminders if is_user_facing_story_event(event) and (not current or event.event_id != current.event_id)], limit=2)
    if not memories and current_text:
        memories = ["No earlier event is needed to understand this moment."]
    tab_events = {
        "story_now": [current] if current else [],
        "relationships": [event for event in recent_events if event.event_type == "relationship_changes"],
        "timeline": [event for event in (previous, current) if event],
        "emotion": [current] if current else [],
        "cause_effect": [event for event in (previous, current) if event],
        "object": [event for event in recent_events if event.event_type == "object_becomes_important"],
        "memory": [event for event in state.memory_reminders if is_user_facing_story_event(event) and (not current or event.event_id != current.event_id)],
    }
    for tab, events in tab_events.items():
        logger.info("[STORY STATE TAB] tab=%s events=%s claim_ids=%s", tab, [event.event_id for event in events], sorted({claim_id for event in events for claim_id in event.semantic_claim_ids}))
    return PresentedStoryTabs(
        story_now=story_now,
        relationships=relationships,
        previous_event=_clean(previous.summary) if previous else None,
        current_event=current_text,
        # An unresolved thread can be shown as the next likely beat; absence
        # means the UI simply hides this optional line rather than inventing one.
        next_event=_first_clean([event.summary for event in state.open_story_threads if is_user_facing_story_event(event) and (not current or event.event_id != current.event_id)]),
        emotion=emotion,
        cause_effect=causes,
        objects=_clean_unique(object_explanations, limit=6),
        memories=memories,
    )
