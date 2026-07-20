"""Whole-work ingestion, entity resolution, graph construction, and retrieval."""
from __future__ import annotations

from collections import defaultdict

from knowledge_engine.embeddings import EmbeddingProvider, HashEmbeddingProvider, cosine_similarity
from knowledge_engine.models import (
    BookIngestionRequest, EntityMemory, EntityMention, Evidence, GraphEdge, GraphNode,
    MovieIngestionRequest, QuestionRequest, RelationshipMention, RetrievalContext,
    Segment, SourceSpan, WorkKnowledge, WorkKind, WorkStatus,
)
from knowledge_engine.store import InMemoryKnowledgeRepository, KnowledgeRepository


class WorkNotReadyError(RuntimeError):
    """Raised when a caller asks before the entire source has been ingested."""


class KnowledgeEngine:
    """NotebookLM-style source-first engine; query paths are read-only."""

    def __init__(self, repository: KnowledgeRepository | None = None, embeddings: EmbeddingProvider | None = None) -> None:
        self._repository = repository or InMemoryKnowledgeRepository()
        self._embeddings = embeddings or HashEmbeddingProvider()

    def ingest_movie(self, request: MovieIngestionRequest) -> WorkKnowledge:
        self._validate_movie(request)
        return self._build(request.work_id, WorkKind.MOVIE, request.scene_segments, request.entities, request.relationships)

    def ingest_book(self, request: BookIngestionRequest) -> WorkKnowledge:
        self._validate_book(request)
        return self._build(request.work_id, WorkKind.BOOK, request.paragraphs, request.entities, request.relationships)

    def retrieve(self, request: QuestionRequest) -> RetrievalContext:
        knowledge = self._repository.get(request.work_id)
        if knowledge is None or knowledge.status is not WorkStatus.READY:
            raise WorkNotReadyError("whole_work_ingestion_required")
        current = self._current_segment(knowledge, request)
        query_vector = self._embeddings.embed(request.question)
        ranked = sorted(
            knowledge.segments,
            key=lambda segment: cosine_similarity(query_vector, knowledge.vectors[segment.id]),
            reverse=True,
        )
        related = self._unique_segments([current, *ranked], request.max_segments)
        previous = self._previous_segments(knowledge.segments, current, 2)
        entity_ids = self._entity_ids_for(request.question, related, knowledge.entities)
        entities = tuple(entity for entity in knowledge.entities if entity.id in entity_ids)
        relationships = tuple(edge for edge in knowledge.edges if edge.source_id in entity_ids or edge.target_id in entity_ids)
        timeline = self._timeline_slice(knowledge.segments, current, related)
        return RetrievalContext(knowledge.work_id, current, previous, related, entities, relationships, timeline)

    def _build(self, work_id: str, kind: WorkKind, segments: tuple[Segment, ...], mentions: tuple[EntityMention, ...], relationships: tuple[RelationshipMention, ...]) -> WorkKnowledge:
        entities = self._resolve_entities(segments, mentions)
        nodes = self._nodes(segments, entities)
        edges = self._edges(segments, relationships, entities)
        vectors = {segment.id: self._embeddings.embed(self._segment_text(segment)) for segment in segments}
        knowledge = WorkKnowledge(work_id, kind, WorkStatus.READY, segments, entities, nodes, edges, vectors)
        self._repository.save(knowledge)
        return knowledge


    @staticmethod
    def _validate_movie(request: MovieIngestionRequest) -> None:
        if request.expected_duration_seconds <= 0 or not request.scene_segments:
            raise ValueError("movie_requires_detected_scenes")
        latest = max(segment.span.end or 0 for segment in request.scene_segments)
        if latest < request.expected_duration_seconds:
            raise ValueError("movie_ingestion_incomplete")

    @staticmethod
    def _validate_book(request: BookIngestionRequest) -> None:
        if request.expected_pages <= 0 or not request.paragraphs:
            raise ValueError("book_requires_detected_paragraphs")
        pages = {page for segment in request.paragraphs for page in range(segment.span.page_start or 0, (segment.span.page_end or 0) + 1)}
        if not all(page in pages for page in range(1, request.expected_pages + 1)):
            raise ValueError("book_ingestion_incomplete")

    @staticmethod
    def _resolve_entities(segments: tuple[Segment, ...], mentions: tuple[EntityMention, ...]) -> tuple[EntityMemory, ...]:
        grouped: dict[tuple[str, str], list[EntityMention]] = defaultdict(list)
        for mention in mentions:
            grouped[(mention.kind.casefold(), mention.name.casefold())].append(mention)
        result = []
        for index, ((kind, name), group) in enumerate(grouped.items(), start=1):
            appearances = [segment for segment in segments if any(value.casefold() in segment.text.casefold() for value in (name, *[alias for item in group for alias in item.aliases]))]
            attributes = {key: value for item in group for key, value in item.attributes.items()}
            first = appearances[0].span if appearances else group[0].evidence.span
            latest = appearances[-1].span if appearances else group[-1].evidence.span
            aliases = tuple(dict.fromkeys(alias for item in group for alias in item.aliases))
            result.append(EntityMemory(f"entity:{index}", group[0].name, kind, aliases, attributes, first, latest, tuple(segment.id for segment in appearances)))
        return tuple(result)

    @staticmethod
    def _nodes(segments: tuple[Segment, ...], entities: tuple[EntityMemory, ...]) -> tuple[GraphNode, ...]:
        entity_nodes = [GraphNode(entity.id, entity.kind, entity.canonical_name, {"aliases": entity.aliases, "attributes": entity.attributes}) for entity in entities]
        segment_nodes = [GraphNode(segment.id, "scene" if segment.span.start is not None else "paragraph", segment.text[:120], {"span": segment.span, "importance": segment.importance}) for segment in segments]
        return tuple([*entity_nodes, *segment_nodes])

    @staticmethod
    def _edges(segments: tuple[Segment, ...], relationships: tuple[RelationshipMention, ...], entities: tuple[EntityMemory, ...]) -> tuple[GraphEdge, ...]:
        by_name = {entity.canonical_name.casefold(): entity.id for entity in entities}
        edges = []
        for index, relation in enumerate(relationships, start=1):
            subject = by_name.get(relation.subject.casefold())
            object_ = by_name.get(relation.object.casefold())
            if subject and object_:
                edges.append(GraphEdge(f"edge:{index}", subject, relation.predicate, object_, relation.evidence))
        for segment in segments:
            for entity in entities:
                if entity.canonical_name.casefold() in segment.text.casefold():
                    edges.append(GraphEdge(f"mentions:{segment.id}:{entity.id}", segment.id, "mentions", entity.id, Evidence(segment.text, segment.span)))
        return tuple(edges)

    @staticmethod
    def _current_segment(knowledge: WorkKnowledge, request: QuestionRequest) -> Segment | None:
        if request.timestamp_seconds is not None:
            return next((segment for segment in knowledge.segments if (segment.span.start or 0) <= request.timestamp_seconds <= (segment.span.end or 0)), None)
        if request.page_number is not None:
            return next((segment for segment in knowledge.segments if (segment.span.page_start or 0) <= request.page_number <= (segment.span.page_end or 0)), None)
        return None

    @staticmethod
    def _previous_segments(segments: tuple[Segment, ...], current: Segment | None, count: int) -> tuple[Segment, ...]:
        if current is None:
            return ()
        index = segments.index(current)
        return segments[max(0, index - count):index]

    @staticmethod
    def _unique_segments(candidates: list[Segment | None], limit: int) -> tuple[Segment, ...]:
        seen: set[str] = set()
        return tuple(segment for segment in candidates if segment and not (segment.id in seen or seen.add(segment.id)))[:limit]

    @staticmethod
    def _entity_ids_for(question: str, segments: tuple[Segment, ...], entities: tuple[EntityMemory, ...]) -> set[str]:
        haystack = " ".join([question, *(segment.text for segment in segments)]).casefold()
        return {entity.id for entity in entities if any(term.casefold() in haystack for term in (entity.canonical_name, *entity.aliases))}

    @staticmethod
    def _timeline_slice(segments: tuple[Segment, ...], current: Segment | None, related: tuple[Segment, ...]) -> tuple[Segment, ...]:
        selected = {segment.id for segment in related}
        if current:
            selected.add(current.id)
        return tuple(segment for segment in segments if segment.id in selected)

    @staticmethod
    def _segment_text(segment: Segment) -> str:
        return " ".join([segment.text, *segment.participants, *segment.objects, *segment.emotions, *segment.causes, *segment.effects])
