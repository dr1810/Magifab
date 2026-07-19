"""Regression coverage for catalog-backed companion presentation.

These tests intentionally use an empty perception result: the catalog must
continue to describe the active scene when every vision model has no match.
"""
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
from services.story_event_extractor import StoryEventExtractor
from services.story_state_manager import StoryStateManager
from schemas.story_state import StoryState
from pathlib import Path


def _presentation(movie_id: str, scene_id: str, timestamp_seconds: float, tmp_path: Path):
    knowledge = MovieKnowledgeProvider().get(movie_id)
    assert knowledge is not None
    perception = UnifiedSceneRepresentation()
    matches = SemanticMatchingService(Settings()).match(
        perception, knowledge, scene_id=scene_id, timestamp_seconds=timestamp_seconds,
    )
    observation = FrameObservation(
        id=f"observation-{scene_id}", movie_id=movie_id, scene_id=scene_id,
        frame_hash="a" * 32, timestamp_seconds=timestamp_seconds,
        model_sources=["catalog_test"],
    )
    claims = SemanticGraphBuilder().build(
        observation=observation, perception=perception, matches=matches, existing=knowledge,
    )
    prepared_knowledge = knowledge.model_copy(update={"semantic_claims": claims})
    context = ReasoningContextBuilder().build(
        knowledge=prepared_knowledge, scene_id=scene_id, timestamp_seconds=timestamp_seconds,
        accessibility_profile=AccessibilityProfile(),
    )
    events = StoryEventExtractor().extract(context, StoryState(movie_id=movie_id))
    state = StoryStateManager(tmp_path, 1).update(movie_id, scene_id, timestamp_seconds, events).state
    return AccessibilityReasoningEngine(cooldown_seconds=0).reason(
        AccessibilityReasoningRequest(story_state=state, accessibility_profile=AccessibilityProfile(), companion_profile=CompanionProfile()),
    )


def test_big_buck_bunny_catalog_character_card_and_timeline_survive_empty_perception(tmp_path):
    presentation = _presentation("bigBuckBunny", "bbb-01", 5.0, tmp_path)

    assert [card.name for card in presentation.character_cards] == ["Big Buck Bunny"]
    assert presentation.character_cards[0].reminder == "Seen in 3 important story moments."
    assert presentation.timeline_summary is not None
    assert presentation.timeline_summary.summary == "Big Buck Bunny's quiet forest routine."
    assert presentation.prompt_bubbles
    assert all("sky" not in prompt.question.lower() for prompt in presentation.prompt_bubbles)


def test_sprite_fright_scene_window_limits_cards_to_its_catalog_cast(tmp_path):
    presentation = _presentation("spriteFright", "sf-01", 5.0, tmp_path)

    assert [card.name for card in presentation.character_cards] == ["Ellie", "Rex", "Jay", "Victoria", "Phil"]
    assert presentation.timeline_summary is not None
    assert presentation.timeline_summary.summary == "The teenagers enter the isolated forest."
    assert presentation.prompt_bubbles
