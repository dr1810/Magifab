"""Builds persisted drawer state from StoryState, never semantic claims."""
from schemas.story_state import StoryState, is_user_facing_story_event
from schemas.timeline_memory import TimelineDrawerState


class DrawerStateBuilder:
    def build(self, state: StoryState, start_timestamp: float) -> TimelineDrawerState:
        return TimelineDrawerState(
            start_timestamp=start_timestamp,
            story_so_far=[event.summary for event in state.story_so_far[-20:] if is_user_facing_story_event(event)],
            current_characters=[character.name for character in state.known_characters.values() if character.current_visibility],
            current_emotions=list(state.active_emotions.values()),
            current_relationships=[relationship.summary for relationship in state.known_relationships.values()],
            current_objects=[item.name for item in state.known_objects.values()],
            unresolved_questions=[event.summary for event in state.open_story_threads if is_user_facing_story_event(event)],
            important_memories=[event.summary for event in state.memory_reminders[-8:] if is_user_facing_story_event(event)],
        )
