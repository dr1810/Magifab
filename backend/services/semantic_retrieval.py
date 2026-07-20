"""NotebookLM-style semantic evidence index for prepared movies and books."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from threading import Lock
from typing import Protocol

from schemas.interval_state import IntervalState


class SemanticEmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[tuple[float, ...]]: ...
    def embed_query(self, text: str) -> tuple[float, ...]: ...


@dataclass(frozen=True)
class SemanticChunk:
    id: str
    kind: str
    text: str
    interval_id: str
    start_time: float
    end_time: float | None
    entities: tuple[str, ...]
    relationships: tuple[str, ...]
    source: str


@dataclass(frozen=True)
class IndexedChunk:
    chunk: SemanticChunk
    vector: tuple[float, ...]


class SemanticRetrievalIndex:
    """Persists typed chunks and vectors; query paths only score existing evidence."""

    def __init__(self, root: Path, embeddings: SemanticEmbeddingProvider, max_chunk_characters: int = 900) -> None:
        self._root = root
        self._embeddings = embeddings
        self._max_chunk_characters = max_chunk_characters
        self._lock = Lock()

    def build(self, work_id: str, states: list[IntervalState], extra_chunks: tuple[SemanticChunk, ...] = ()) -> None:
        chunks = [*_chunks_from_states(states, self._max_chunk_characters), *extra_chunks]
        fingerprint = _fingerprint(chunks)
        with self._lock:
            existing = self._load(work_id)
            if existing and existing[0] == fingerprint:
                return
            vectors = self._embeddings.embed_documents([chunk.text for chunk in chunks])
            if len(vectors) != len(chunks):
                raise ValueError("embedding_count_mismatch")
            self._save(work_id, fingerprint, [IndexedChunk(chunk, vector) for chunk, vector in zip(chunks, vectors, strict=True)])

    def retrieve(self, work_id: str, query: str, *, current_interval_id: str, allowed_kinds: tuple[str, ...], entity_hints: tuple[str, ...] = (), limit: int = 8) -> list[SemanticChunk]:
        with self._lock:
            loaded = self._load(work_id)
        if loaded is None:
            raise ValueError("semantic_index_not_preprocessed")
        _, indexed = loaded
        query_vector = self._embeddings.embed_query(query)
        permitted = [item for item in indexed if item.chunk.kind in allowed_kinds]
        ranked = sorted(permitted, key=lambda item: _score(item, query_vector, current_interval_id, entity_hints), reverse=True)
        selected = _diverse(ranked, limit)
        return [item.chunk for item in selected]

    def _path(self, work_id: str) -> Path:
        return self._root / f"{sha256(work_id.encode('utf-8')).hexdigest()}.json"

    def _load(self, work_id: str) -> tuple[str, list[IndexedChunk]] | None:
        path = self._path(work_id)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        chunks = [IndexedChunk(SemanticChunk(**{**item["chunk"], "entities": tuple(item["chunk"]["entities"]), "relationships": tuple(item["chunk"]["relationships"])}), tuple(item["vector"])) for item in payload["chunks"]]
        return payload["fingerprint"], chunks

    def _save(self, work_id: str, fingerprint: str, chunks: list[IndexedChunk]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        target = self._path(work_id)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps({"fingerprint": fingerprint, "chunks": [asdict(item) for item in chunks]}, separators=(",", ":")), encoding="utf-8")
        temporary.replace(target)


def _chunks_from_states(states: list[IntervalState], maximum: int) -> list[SemanticChunk]:
    chunks: list[SemanticChunk] = []
    for state in states:
        entities = tuple(dict.fromkeys([*(card.name for card in state.characters), *state.semanticMemoryAfter.active_characters]))
        relationships = tuple(dict.fromkeys([*(item.summary for item in state.relationships), *state.semanticMemoryAfter.relationships]))
        base = {"interval_id": state.metadata.interval_id, "start_time": state.metadata.start_time, "end_time": state.metadata.end_time, "entities": entities, "relationships": relationships}
        _append(chunks, "scene", state.storyState.scene_summary, "scene_summary", base, maximum)
        _append(chunks, "timeline", state.timelineMemory.current_event, "timeline_event", base, maximum)
        _append(chunks, "dialogue", state.conversationContext.scene_explanation, "dialogue", base, maximum)
        for index, emotion in enumerate(state.accessibilityHints.emotions):
            _append(chunks, "emotion", emotion.summary, f"emotion:{index}", base, maximum)
        for index, vocabulary in enumerate(state.accessibilityHints.vocabulary):
            _append(chunks, "glossary", f"{vocabulary.term}: {vocabulary.simple_definition}", f"glossary:{index}", base, maximum)
        for index, relationship in enumerate(relationships):
            _append(chunks, "relationship", relationship, f"relationship:{index}", base, maximum)
        for index, event in enumerate(state.semanticMemoryAfter.story_events):
            _append(chunks, "event", event, f"event:{index}", base, maximum)
        for index, object_name in enumerate(state.semanticMemoryAfter.important_objects):
            _append(chunks, "object", object_name, f"object:{index}", base, maximum)
        for character in state.characters:
            _append(chunks, "character", f"{character.name}. {character.reminder}", f"character:{character.character_id}", base, maximum)
    return chunks


def _append(chunks: list[SemanticChunk], kind: str, text: str | None, suffix: str, base: dict[str, object], maximum: int) -> None:
    cleaned = " ".join((text or "").split())[:maximum]
    if not cleaned:
        return
    chunks.append(SemanticChunk(id=f"{base['interval_id']}:{suffix}", kind=kind, text=cleaned, interval_id=str(base["interval_id"]), start_time=float(base["start_time"]), end_time=base["end_time"], entities=base["entities"], relationships=base["relationships"], source=f"interval:{base['interval_id']}"))


def _score(item: IndexedChunk, query: tuple[float, ...], current_id: str, entity_hints: tuple[str, ...]) -> float:
    semantic = sum(left * right for left, right in zip(item.vector, query, strict=True))
    current_bonus = .06 if item.chunk.interval_id == current_id else 0.0
    entity_bonus = .08 if any(hint.casefold() in {entity.casefold() for entity in item.chunk.entities} for hint in entity_hints) else 0.0
    return semantic + current_bonus + entity_bonus


def _diverse(indexed: list[IndexedChunk], limit: int) -> list[IndexedChunk]:
    selected: list[IndexedChunk] = []
    seen: set[tuple[str, str]] = set()
    for item in indexed:
        key = (item.chunk.interval_id, item.chunk.kind)
        if key in seen:
            continue
        seen.add(key)
        selected.append(item)
        if len(selected) == limit:
            return selected
    return selected


def _fingerprint(chunks: list[SemanticChunk]) -> str:
    return sha256(json.dumps([asdict(chunk) for chunk in chunks], sort_keys=True).encode("utf-8")).hexdigest()
