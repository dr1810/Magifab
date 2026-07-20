from pathlib import Path

from schemas.interval_state import (
    ConversationContext,
    IntervalCacheMetadata,
    IntervalMetadata,
    IntervalSemanticMemory,
    IntervalTimelineMemory,
    IntervalState,
    IntervalStoryState,
)
from services.interval_state_store import IntervalStateRepository


def _state(interval_number: int) -> IntervalState:
    start = interval_number * 30.0
    return IntervalState(
        metadata=IntervalMetadata(
            interval_id=f"movie:interval:{interval_number}", catalog_scene_id=None,
            movie_id="movie", start_time=start, end_time=start + 30,
            interval_number=interval_number, knowledge_revision=1,
        ),
        storyState=IntervalStoryState(current_goal="Understand the interval", current_interval_id=f"movie:interval:{interval_number}"),
        conversationContext=ConversationContext(scene_explanation="Prepared context."),
        semanticMemoryBefore=IntervalSemanticMemory(),
        semanticMemoryAfter=IntervalSemanticMemory(),
        timelineMemory=IntervalTimelineMemory(),
        cacheMetadata=IntervalCacheMetadata(semantic_cache_key="test", knowledge_source="test", semantic_map_cached=False),
    )


def test_repository_retrieves_immutable_intervals_in_any_playback_order(tmp_path: Path):
    repository = IntervalStateRepository(tmp_path, 1)
    first = repository.save(_state(0))
    later = repository.save(_state(3))

    # Forward, rewind, and jump are ordinary independent reads. No mutable
    # timestamp is advanced and no regression assertion can be triggered.
    assert repository.load("movie", 31).metadata.interval_id == later.metadata.interval_id
    assert repository.load("movie", 2).metadata.interval_id == first.metadata.interval_id
    assert repository.load("movie", 39).metadata.interval_id == later.metadata.interval_id


def test_repository_rejects_metadata_outside_its_fixed_interval(tmp_path: Path):
    repository = IntervalStateRepository(tmp_path, 1)
    invalid = _state(1).model_copy(update={"metadata": IntervalMetadata(
        interval_id="movie:interval:1", catalog_scene_id=None, movie_id="movie",
        start_time=0, end_time=10, interval_number=1, knowledge_revision=1,
    )})
    try:
        repository.save(invalid)
    except ValueError as error:
        assert "interval number" in str(error)
    else:
        raise AssertionError("repository must validate interval metadata")
