from schemas.accessibility_reasoning import AccessibilityProfile
from schemas.reasoning_context import ReasoningContext, ReasoningEntity
from schemas.semantic_graph import SemanticClaim
from services.sliding_window_memory import SlidingWindowMemoryManager


def _claim(id: str, kind: str, timestamp: float, subject: str, value: str = "") -> SemanticClaim:
    return SemanticClaim(
        id=id, kind=kind, scene_id=f"scene-{int(timestamp)}", timestamp_seconds=timestamp,
        subject_id=subject, predicate="appears" if kind == "character_present" else "happens",
        value=value, confidence=1, observation_ids=["observation-1"],
    )


def _context(timestamp: float, names: list[tuple[str, str]], claims: list[SemanticClaim]) -> ReasoningContext:
    return ReasoningContext(
        movie_id="movie", scene_id=f"scene-{int(timestamp)}", timestamp_seconds=timestamp,
        accessibility_profile=AccessibilityProfile(), semantic_scene=claims,
        active_characters=[ReasoningEntity(id=id, name=name, confidence=1, claim_ids=[id]) for id, name in names],
    )


def test_recurrent_memory_merges_characters_and_selects_plot_changes():
    manager = SlidingWindowMemoryManager()
    ellie = _claim("ellie-present", "character_present", 5, "ellie", "Ellie appears")
    first = manager.update(_context(5, [("ellie", "Ellie")], [ellie]), frame_hash="a" * 32)

    rex = _claim("rex-present", "character_present", 15, "rex", "Rex appears")
    event = _claim("rex-enters", "event", 15, "rex", "Rex enters the forest")
    second = manager.update(_context(15, [("ellie", "Ellie"), ("rex", "Rex")], [rex, event]), frame_hash="b" * 32)

    assert first.window.start_timestamp == 0
    assert first.window.end_timestamp == 10
    assert second.window.captured_frames[0].timestamp_seconds == 15
    assert second.new_characters == ["Rex"]
    # Long-term character knowledge is owned by PreprocessingStoryBuilder; the
    # sliding manager only reports this window's change signal.
    assert second.long_term.known_characters == []
    assert "rex-enters" in second.selected_claim_ids


def test_static_background_details_do_not_enter_long_term_memory_or_attention():
    manager = SlidingWindowMemoryManager()
    sky = _claim("sky", "event", 5, "world", "The sky color changes")
    update = manager.update(_context(5, [], [sky]))

    assert update.window.events == []
    assert update.long_term.important_events == []
    assert update.selected_claim_ids == []


def test_replaying_the_same_window_is_idempotent():
    manager = SlidingWindowMemoryManager()
    ellie = _claim("ellie-present", "character_present", 5, "ellie", "Ellie appears")
    context = _context(5, [("ellie", "Ellie")], [ellie])

    first = manager.update(context)
    replay = manager.update(context)

    assert replay == first
