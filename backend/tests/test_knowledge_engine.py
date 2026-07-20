import pytest

from knowledge_engine.engine import KnowledgeEngine, WorkNotReadyError
from knowledge_engine.models import (
    BookIngestionRequest, EntityMention, Evidence, MovieIngestionRequest,
    QuestionRequest, RelationshipMention, Segment, SourceSpan,
)
from knowledge_engine.store import FileKnowledgeRepository


def _movie_segment(identifier: str, start: float, end: float, text: str) -> Segment:
    return Segment(identifier, text, SourceSpan("movie", start=start, end=end), importance=.9)


def test_movie_retrieval_uses_whole_work_entity_and_timeline_memory():
    engine = KnowledgeEngine()
    ellie = EntityMention("Ellie", "character", Evidence("Ellie meets Rex.", SourceSpan("movie", start=0, end=10)), aliases=("Eleanor",), attributes={"role": "explorer"})
    rex = EntityMention("Rex", "character", Evidence("Rex arrives.", SourceSpan("movie", start=0, end=10)))
    engine.ingest_movie(MovieIngestionRequest(
        "movie-1", 30,
        (_movie_segment("scene-1", 0, 10, "Ellie meets Rex in the garden."), _movie_segment("scene-2", 10, 20, "Rex loses the map."), _movie_segment("scene-3", 20, 30, "Ellie finds the map and helps Rex.")),
        entities=(ellie, rex),
        relationships=(RelationshipMention("Ellie", "helps", "Rex", Evidence("Ellie finds the map and helps Rex.", SourceSpan("movie", start=20, end=30))),),
    ))

    context = engine.retrieve(QuestionRequest("movie-1", "Where did Eleanor first meet Rex?", timestamp_seconds=25))

    assert context.current_segment.id == "scene-3"
    assert [segment.id for segment in context.previous_segments] == ["scene-1", "scene-2"]
    assert "scene-1" in {segment.id for segment in context.related_segments}
    assert context.entities[0].canonical_name == "Ellie"
    assert context.entities[0].attributes["role"] == "explorer"
    assert context.relationships[0].predicate == "helps"


def test_incomplete_work_is_rejected_before_any_question_can_be_answered():
    engine = KnowledgeEngine()
    with pytest.raises(ValueError, match="movie_ingestion_incomplete"):
        engine.ingest_movie(MovieIngestionRequest("partial", 100, (_movie_segment("scene", 0, 20, "Only part of the film."),)))
    with pytest.raises(WorkNotReadyError, match="whole_work_ingestion_required"):
        engine.retrieve(QuestionRequest("partial", "What happened?"))


def test_book_ingestion_requires_all_pages_and_supports_historical_retrieval():
    engine = KnowledgeEngine()
    paragraphs = (
        Segment("p1", "Mira receives a letter.", SourceSpan("book", page_start=1, page_end=1)),
        Segment("p2", "Mira hides the letter from Theo.", SourceSpan("book", page_start=2, page_end=2)),
    )
    knowledge = engine.ingest_book(BookIngestionRequest("book-1", 2, paragraphs, entities=(EntityMention("Mira", "character", Evidence("Mira receives a letter.", SourceSpan("book", page_start=1, page_end=1))),)))
    context = engine.retrieve(QuestionRequest("book-1", "What did Mira receive earlier?", page_number=2))

    assert knowledge.status.value == "ready"
    assert context.current_segment.id == "p2"
    assert context.previous_segments[0].id == "p1"
    assert context.related_segments[0].id == "p2"


def test_file_repository_preserves_entity_memory_and_vectors(tmp_path):
    repository = FileKnowledgeRepository(tmp_path)
    engine = KnowledgeEngine(repository)
    engine.ingest_movie(MovieIngestionRequest("durable", 10, (_movie_segment("scene", 0, 10, "Noor finds the compass."),)))

    restored = repository.get("durable")

    assert restored is not None
    assert restored.segments[0].id == "scene"
    assert restored.vectors["scene"]
