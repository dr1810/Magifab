from pathlib import Path
import pytest

from schemas.accessibility_reasoning import AccessibilityReasoningRequest
from schemas.profiles import AccessibilityProfile, CompanionProfile
from schemas.reasoning_context import ReasoningContext, ReasoningEntity
from schemas.semantic_graph import SemanticClaim
from schemas.story_state import StoryEvent, StoryState
from services.accessibility_reasoning import AccessibilityReasoningEngine
from services.story_event_extractor import StoryEventExtractor
from services.story_state_manager import StoryStateManager


def test_story_state_is_the_only_input_to_accessibility_reasoning(tmp_path: Path):
    claim = SemanticClaim(id="conflict", kind="event", scene_id="bbb-02", timestamp_seconds=160, subject_id="bunny", predicate="teases", value="Rodents begin teasing Bunny", confidence=.9, observation_ids=["frame"])
    context = ReasoningContext(movie_id="bigBuckBunny", scene_id="bbb-02", timestamp_seconds=160, accessibility_profile=AccessibilityProfile(), semantic_scene=[claim], active_characters=[ReasoningEntity(id="bunny", name="Big Buck Bunny", confidence=1, claim_ids=["present"])])
    events = StoryEventExtractor().extract(context, StoryState(movie_id="bigBuckBunny"))
    state = StoryStateManager(tmp_path, 1).update("bigBuckBunny", "bbb-02", 160, events).state
    presentation = AccessibilityReasoningEngine().reason(AccessibilityReasoningRequest(story_state=state, accessibility_profile=AccessibilityProfile(), companion_profile=CompanionProfile()))
    assert state.story_so_far
    assert presentation.live_story is not None
    assert presentation.live_story.current_scene == "bbb-02"
    assert presentation.prompt_bubbles


def test_story_state_rejects_timestamp_regression_and_invalid_relationships(tmp_path: Path):
    manager = StoryStateManager(tmp_path, 1)
    event = StoryEvent(event_id="event-1", timestamp_start=10, timestamp_end=20, importance_score=2, confidence=1, event_type="story_event", semantic_claim_ids=["claim-1"], summary="A story event", is_new=True, requires_memory=True, requires_prompt=True)
    manager.update("movie", "scene", 20, [event])
    with pytest.raises(AssertionError, match="regressed"):
        manager.update("movie", "scene", 10, [])
    invalid_relationship = StoryEvent(event_id="relationship-1", timestamp_start=20, timestamp_end=30, importance_score=2, confidence=1, event_type="relationship_changed", semantic_claim_ids=[], summary="An unsupported relationship", is_new=True, requires_memory=True, requires_prompt=True)
    with pytest.raises(AssertionError, match="supporting semantic claims"):
        manager.update("movie", "scene", 30, [invalid_relationship])
