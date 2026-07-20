"""Immutable domain records for whole-work ingestion and grounded retrieval."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class WorkKind(StrEnum):
    MOVIE = "movie"
    BOOK = "book"


class WorkStatus(StrEnum):
    INGESTING = "ingesting"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True)
class SourceSpan:
    source_id: str
    start: float | None = None
    end: float | None = None
    page_start: int | None = None
    page_end: int | None = None


@dataclass(frozen=True)
class Evidence:
    text: str
    span: SourceSpan
    confidence: float = 1.0


@dataclass(frozen=True)
class Segment:
    id: str
    text: str
    span: SourceSpan
    participants: tuple[str, ...] = ()
    objects: tuple[str, ...] = ()
    location: str | None = None
    emotions: tuple[str, ...] = ()
    causes: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    importance: float = 0.5


@dataclass(frozen=True)
class EntityMention:
    name: str
    kind: str
    evidence: Evidence
    aliases: tuple[str, ...] = ()
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RelationshipMention:
    subject: str
    predicate: str
    object: str
    evidence: Evidence


@dataclass(frozen=True)
class MovieIngestionRequest:
    work_id: str
    expected_duration_seconds: float
    scene_segments: tuple[Segment, ...]
    subtitles: tuple[Evidence, ...] = ()
    entities: tuple[EntityMention, ...] = ()
    relationships: tuple[RelationshipMention, ...] = ()


@dataclass(frozen=True)
class BookIngestionRequest:
    work_id: str
    expected_pages: int
    paragraphs: tuple[Segment, ...]
    entities: tuple[EntityMention, ...] = ()
    relationships: tuple[RelationshipMention, ...] = ()


@dataclass(frozen=True)
class EntityMemory:
    id: str
    canonical_name: str
    kind: str
    aliases: tuple[str, ...]
    attributes: dict[str, str]
    first_appearance: SourceSpan
    latest_appearance: SourceSpan
    important_segment_ids: tuple[str, ...]


@dataclass(frozen=True)
class GraphNode:
    id: str
    kind: str
    label: str
    properties: dict[str, object]


@dataclass(frozen=True)
class GraphEdge:
    id: str
    source_id: str
    predicate: str
    target_id: str
    evidence: Evidence


@dataclass(frozen=True)
class WorkKnowledge:
    work_id: str
    kind: WorkKind
    status: WorkStatus
    segments: tuple[Segment, ...]
    entities: tuple[EntityMemory, ...]
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    vectors: dict[str, tuple[float, ...]]


@dataclass(frozen=True)
class QuestionRequest:
    work_id: str
    question: str
    timestamp_seconds: float | None = None
    page_number: int | None = None
    max_segments: int = 8


@dataclass(frozen=True)
class RetrievalContext:
    work_id: str
    current_segment: Segment | None
    previous_segments: tuple[Segment, ...]
    related_segments: tuple[Segment, ...]
    entities: tuple[EntityMemory, ...]
    relationships: tuple[GraphEdge, ...]
    timeline: tuple[Segment, ...]

