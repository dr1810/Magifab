"""Repository boundary for durable whole-work knowledge snapshots."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Protocol

from knowledge_engine.models import (
    EntityMemory, Evidence, GraphEdge, GraphNode, Segment, SourceSpan,
    WorkKind, WorkKnowledge, WorkStatus,
)


class KnowledgeRepository(Protocol):
    def save(self, knowledge: WorkKnowledge) -> None: ...
    def get(self, work_id: str) -> WorkKnowledge | None: ...


class InMemoryKnowledgeRepository:
    """Test/local adapter. Replace with Postgres + pgvector in deployment."""

    def __init__(self) -> None:
        self._works: dict[str, WorkKnowledge] = {}

    def save(self, knowledge: WorkKnowledge) -> None:
        self._works[knowledge.work_id] = knowledge

    def get(self, work_id: str) -> WorkKnowledge | None:
        return self._works.get(work_id)


class FileKnowledgeRepository:
    """Atomic JSON persistence for a single-node deployment or development."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def save(self, knowledge: WorkKnowledge) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        target = self._path(knowledge.work_id)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(knowledge), default=_json_default, separators=(",", ":")), encoding="utf-8")
        temporary.replace(target)

    def get(self, work_id: str) -> WorkKnowledge | None:
        path = self._path(work_id)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return WorkKnowledge(
            work_id=payload["work_id"], kind=WorkKind(payload["kind"]), status=WorkStatus(payload["status"]),
            segments=tuple(_segment(item) for item in payload["segments"]),
            entities=tuple(_entity(item) for item in payload["entities"]),
            nodes=tuple(GraphNode(**item) for item in payload["nodes"]),
            edges=tuple(_edge(item) for item in payload["edges"]),
            vectors={key: tuple(value) for key, value in payload["vectors"].items()},
        )

    def _path(self, work_id: str) -> Path:
        digest = hashlib.sha256(work_id.encode("utf-8")).hexdigest()
        return self._root / f"{digest}.json"


def _span(payload: dict[str, object]) -> SourceSpan:
    return SourceSpan(**payload)


def _segment(payload: dict[str, object]) -> Segment:
    return Segment(**{**payload, "span": _span(payload["span"])})


def _entity(payload: dict[str, object]) -> EntityMemory:
    return EntityMemory(**{**payload, "first_appearance": _span(payload["first_appearance"]), "latest_appearance": _span(payload["latest_appearance"])})


def _edge(payload: dict[str, object]) -> GraphEdge:
    evidence = payload["evidence"]
    return GraphEdge(**{**payload, "evidence": Evidence(**{**evidence, "span": _span(evidence["span"])})})


def _json_default(value: object) -> object:
    if isinstance(value, (WorkKind, WorkStatus)):
        return value.value
    raise TypeError(f"Cannot serialize {type(value).__name__}")
