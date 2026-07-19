from pathlib import Path

from schemas.accessibility_reasoning import AccessibilityReasoningRequest
from schemas.profiles import AccessibilityProfile, CompanionProfile
from schemas.reasoning_context import ReasoningContext, ReasoningEntity
from schemas.semantic_graph import SemanticClaim
from schemas.story_state import StoryEvent, StoryState, is_user_facing_story_event
from services.accessibility_reasoning import AccessibilityReasoningEngine
from services.story_event_extractor import StoryEventExtractor
from services.story_state_manager import PreprocessingStoryBuilder


def test_story_state_is_the_only_input_to_accessibility_reasoning(tmp_path: Path):
    claim = SemanticClaim(id="conflict", kind="event", scene_id="bbb-02", timestamp_seconds=160, subject_id="bunny", predicate="teases", value="Rodents begin teasing Bunny", confidence=.9, observation_ids=["frame"])
    context = ReasoningContext(movie_id="bigBuckBunny", scene_id="bbb-02", timestamp_seconds=160, accessibility_profile=AccessibilityProfile(), semantic_scene=[claim], active_characters=[ReasoningEntity(id="bunny", name="Big Buck Bunny", confidence=1, claim_ids=["present"])])
    events = StoryEventExtractor().extract(context, StoryState(movie_id="bigBuckBunny"))
    state = PreprocessingStoryBuilder(tmp_path, 1).advance("bigBuckBunny", "bbb-02", 160, events).state
    interval = AccessibilityReasoningEngine().reason(AccessibilityReasoningRequest(story_state=state, accessibility_profile=AccessibilityProfile(), companion_profile=CompanionProfile()))
    assert state.story_so_far
    assert interval.storyState.current_interval_id == "bbb-02"
    assert interval.prompts.prompt_bubbles


def test_preprocessing_builder_requires_order_but_playback_repository_does_not(tmp_path: Path):
    builder = PreprocessingStoryBuilder(tmp_path, 1)
    event = StoryEvent(event_id="event-1", timestamp_start=10, timestamp_end=20, importance_score=2, confidence=1, event_type="story_event", semantic_claim_ids=["claim-1"], summary="A story event", is_new=True, requires_memory=True, requires_prompt=True)
    builder.advance("movie", "scene", 20, [event])
    # The restriction is isolated to chronological preprocessing writes.
    try:
        builder.advance("movie", "scene", 10, [])
    except AssertionError as error:
        assert "preprocessing" in str(error)
    else:
        raise AssertionError("preprocessing ordering must be validated")
    invalid_relationship = StoryEvent(event_id="relationship-1", timestamp_start=20, timestamp_end=30, importance_score=2, confidence=1, event_type="relationship_changed", semantic_claim_ids=[], summary="An unsupported relationship", is_new=True, requires_memory=True, requires_prompt=True)
    try:
        builder.advance("movie", "scene", 30, [invalid_relationship])
    except AssertionError as error:
        assert "supporting semantic claims" in str(error)
    else:
        raise AssertionError("relationships require supporting semantic claims")


def test_internal_semantic_bookkeeping_is_not_a_presentation_event():
    event = StoryEvent(
        event_id="internal", timestamp_start=0, timestamp_end=0,
        importance_score=0, confidence=1, event_type="semantic_observation",
        semantic_claim_ids=[], summary="Existing semantic state remains active",
        is_new=True, requires_memory=False, requires_prompt=False,
    )
    assert not is_user_facing_story_event(event)
