from schemas.story_state import CharacterState, StoryEvent, StoryState
from schemas.profiles import AccessibilityProfile
from services.accessibility_reasoning import PromptRankingEngine
from services.story_state_presenter import StoryStatePresenter


def test_presenter_removes_internal_placeholders_deduplicates_and_infers_goal():
    event = StoryEvent(event_id="event", timestamp_start=10, timestamp_end=10, importance_score=3, confidence=1, event_type="conflict_begins", semantic_claim_ids=["claim"], summary="The group enters the forest.", is_new=True, requires_memory=True, requires_prompt=True)
    state = StoryState(
        movie_id="movie", current_timestamp=10,
        known_characters={"rex": CharacterState(id="rex", name="Rex", first_seen_timestamp=10, last_seen_timestamp=10)},
        story_so_far=[event, event.model_copy(update={"event_id": "event-2", "summary": "appears in"}), event],
        recent_events=[event], memory_reminders=[event, event],
    )
    presented = StoryStatePresenter().present(state)
    assert presented.current_goal.startswith("Understand")
    assert presented.story_summary == ["The group enters the forest."]
    assert presented.memory_reminders == ["The group enters the forest."]
    assert [(character.name, character.role) for character in presented.active_characters] == [("Rex", "New character")]
    assert presented.tabs.story_now
    assert presented.tabs.relationships
    assert presented.tabs.current_event == "The group enters the forest."
    assert presented.tabs.emotion
    assert presented.tabs.cause_effect
    assert presented.tabs.objects
    assert len(presented.tabs.memories) <= 2
    assert "claim" not in presented.model_dump_json()
    assert "appears in" not in presented.model_dump_json().lower()


def test_prompt_ranking_returns_four_diverse_contextual_prompts():
    state = StoryState(
        movie_id="movie", current_timestamp=12,
        known_characters={"rex": CharacterState(id="rex", name="Rex", first_seen_timestamp=1, last_seen_timestamp=12)},
    )
    prompts = PromptRankingEngine().rank(state, AccessibilityProfile(), limit=4)
    assert len(prompts) == 4
    assert [prompt.kind for prompt in prompts] == ["critical", "memory", "emotion", "prediction"]
    assert all(prompt.timestamp_start == 12 for prompt in prompts)
    assert len({prompt.id for prompt in prompts}) == len(prompts)
    assert not {"Who is this?", "What happened?", "What is this?"} & {prompt.question for prompt in prompts}
