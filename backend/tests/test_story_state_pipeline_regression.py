"""Sequential catalog-pipeline regressions for the canonical StoryState architecture."""
from pathlib import Path

import pytest

from config import Settings
from schemas.accessibility_reasoning import AccessibilityReasoningRequest
from schemas.fusion import UnifiedSceneRepresentation
from schemas.observation import FrameObservation
from schemas.profiles import AccessibilityProfile, CompanionProfile
from services.accessibility_reasoning import AccessibilityReasoningEngine
from services.movie_knowledge_provider import MovieKnowledgeProvider
from services.reasoning_context_builder import ReasoningContextBuilder
from services.semantic_graph_builder import SemanticGraphBuilder
from services.semantic_matching import SemanticMatchingService
from services.sliding_window_memory import SlidingWindowMemoryManager
from services.story_event_extractor import StoryEventExtractor
from services.story_state_manager import PreprocessingStoryBuilder
from services.timeline_memory import TimelineMemoryService


def _context(movie_id: str, scene_id: str, timestamp: float):
    knowledge = MovieKnowledgeProvider().get(movie_id)
    assert knowledge is not None
    matches = SemanticMatchingService(Settings()).match(UnifiedSceneRepresentation(), knowledge, scene_id=scene_id, timestamp_seconds=timestamp)
    observation = FrameObservation(id=f"{movie_id}:{scene_id}:{timestamp}", movie_id=movie_id, scene_id=scene_id, frame_hash="a" * 32, timestamp_seconds=timestamp, model_sources=["regression"])
    claims = SemanticGraphBuilder().build(observation=observation, perception=UnifiedSceneRepresentation(), matches=matches, existing=knowledge)
    return ReasoningContextBuilder().build(knowledge=knowledge.model_copy(update={"semantic_claims": claims}), scene_id=scene_id, timestamp_seconds=timestamp, accessibility_profile=AccessibilityProfile(detail_level="more detailed"))


@pytest.mark.parametrize("movie_id,windows", [
    ("bigBuckBunny", [("bbb-01", 5.0), ("bbb-02", 165.0), ("bbb-02", 175.0)]),
    ("spriteFright", [("sf-01", 5.0), ("sf-02", 185.0), ("sf-02", 195.0)]),
])
def test_supported_movie_preprocessing_builds_interval_states_in_order(tmp_path: Path, movie_id, windows):
    manager = PreprocessingStoryBuilder(tmp_path, 1)
    timeline_memory = TimelineMemoryService(tmp_path, 1)
    extractor = StoryEventExtractor()
    sliding = SlidingWindowMemoryManager()
    reasoner = AccessibilityReasoningEngine()
    total_events = []
    prompt_kinds = set()
    previous_count = 0

    for scene_id, timestamp in windows:
        context = _context(movie_id, scene_id, timestamp)
        window = sliding.update(context)
        state_before = manager.get(movie_id)
        events = extractor.extract(context, state_before, window_start=window.window.start_timestamp, window_end=window.window.end_timestamp)
        # Reused semantic evidence is not a user-facing story event and does
        # not create a presentation snapshot of its own.
        assert all(event.event_type != "semantic_observation" for event in events)
        assert all(event.timestamp_start <= event.timestamp_end for event in events)
        assert all(event.timestamp_end <= window.window.end_timestamp for event in events)
        state_changes = [event for event in events if event.requires_memory]
        if state_changes:
            state = manager.advance(movie_id, scene_id, timestamp, state_changes).state
            timeline_memory.write_change(state_before, state, state_changes)
        else:
            state = state_before
        timeline_state = timeline_memory.at(movie_id, timestamp)
        assert timeline_state is not None
        interval = reasoner.reason(AccessibilityReasoningRequest(story_state=timeline_state.story_state, timeline_state=timeline_state, accessibility_profile=context.accessibility_profile, companion_profile=CompanionProfile()))

        assert state.current_timestamp <= timestamp
        assert len(state.story_so_far) >= previous_count
        assert len({event.event_id for event in state.story_so_far}) == len(state.story_so_far)
        assert interval.metadata.start_time == timestamp
        assert not hasattr(interval.storyState, "known_characters")
        assert interval.storyState.current_interval_id == scene_id
        assert all(prompt.id.removeprefix("timeline-prompt:") in {event.event_id for event in state.story_so_far} for prompt in interval.prompts.prompt_bubbles if prompt.id.startswith("timeline-prompt:"))
        assert not any(prompt.id.startswith("fallback:") for prompt in interval.prompts.prompt_bubbles)
        assert all(relationship.supporting_claim_ids for relationship in state.known_relationships.values())
        assert all(character.last_seen_timestamp >= character.first_seen_timestamp and character.total_screen_time >= 0 for character in state.known_characters.values())
        prompt_candidates = [event for event in state.recent_events if event.requires_prompt and event.is_new]
        assert len(interval.prompts.prompt_bubbles) == 4
        assert {prompt.kind for prompt in interval.prompts.prompt_bubbles} == {"critical", "memory", "emotion", "prediction"}
        memory = timeline_memory.get(movie_id)
        assert any(interval.start_timestamp <= timestamp and (interval.end_timestamp is None or timestamp < interval.end_timestamp) for interval in memory.intervals)

        total_events.extend(events)
        prompt_kinds.update(prompt.kind for prompt in interval.prompts.prompt_bubbles)
        previous_count = len(state.story_so_far)

    assert len(total_events) >= len(windows)
    assert len(state.timeline_history) >= 2
    assert state.memory_reminders
    assert prompt_kinds == {"critical", "memory", "emotion", "prediction"}
    assert any(character.total_screen_time > 0 for character in state.known_characters.values())
    assert any(len(character.associated_events) >= 2 for character in state.known_characters.values())
    # Seeking resolves indexed semantic snapshots directly; no interval replay.
    rewind = timeline_memory.at(movie_id, windows[0][1])
    jump = timeline_memory.at(movie_id, windows[-1][1])
    assert rewind is not None and jump is not None
    assert rewind.story_state.current_interval_id == windows[0][0]
    assert jump.story_state.current_interval_id == windows[-1][0]
    assert jump.timestamp == windows[-1][1]
