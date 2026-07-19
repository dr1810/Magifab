from pathlib import Path

from schemas.story_state import StoryEvent, StoryState
from services.story_state_manager import StoryStateManager
from services.timeline_memory import TimelineMemoryService


def _event(event_id: str, timestamp: float, event_type: str = "character_introduced") -> StoryEvent:
    return StoryEvent(
        event_id=event_id, timestamp_start=timestamp, timestamp_end=timestamp,
        importance_score=2, confidence=1, event_type=event_type,
        semantic_claim_ids=[f"claim:{event_id}"], summary=event_id,
        is_new=True, requires_memory=True, requires_prompt=True,
    )


def test_timeline_resolves_identically_for_replay_and_seeking_and_expires_prompts(tmp_path: Path):
    states = StoryStateManager(tmp_path, 1)
    timeline = TimelineMemoryService(tmp_path, 1)
    before = states.get("movie")
    first = states.update("movie", "opening", 5, [_event("introduce-rex", 5)]).state
    timeline.write_change(before, first, [_event("introduce-rex", 5)])
    before = first
    second = states.update("movie", "middle", 40, [_event("group-splits", 40, "conflict_begins")]).state
    timeline.write_change(before, second, [_event("group-splits", 40, "conflict_begins")])

    replay = timeline.at("movie", 10)
    rapid_forward = timeline.at("movie", 41)
    rewind = timeline.at("movie", 10)
    assert replay is not None and rapid_forward is not None and rewind is not None
    assert replay.model_dump() == rewind.model_dump()
    assert replay.story_state.current_scene == "opening"
    assert rapid_forward.story_state.current_scene == "middle"
    assert len({prompt.prompt_id for prompt in rapid_forward.prompts}) == len(rapid_forward.prompts)
    assert all(prompt.end_timestamp is None or prompt.start_timestamp <= prompt.end_timestamp for prompt in rapid_forward.prompts)
    # The introduction prompt is superseded by the next semantic transition.
    assert all(prompt.semantic_event_id != "introduce-rex" for prompt in rapid_forward.prompts)
