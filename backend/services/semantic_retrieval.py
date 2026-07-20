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


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: SemanticChunk
    similarity_score: float


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

    def retrieve(self, work_id: str, query: str, *, current_interval_id: str, allowed_kinds: tuple[str, ...], entity_hints: tuple[str, ...] = (), mode: str = "movie", current_position: float | None = None, current_text: str | None = None, intent: str | None = None, limit: int = 8) -> list[SemanticChunk]:
        return [item.chunk for item in self.retrieve_with_scores(work_id, query, current_interval_id=current_interval_id, allowed_kinds=allowed_kinds, entity_hints=entity_hints, mode=mode, current_position=current_position, current_text=current_text, intent=intent, limit=limit)]

    def retrieve_with_scores(self, work_id: str, query: str, *, current_interval_id: str, allowed_kinds: tuple[str, ...], entity_hints: tuple[str, ...] = (), mode: str = "movie", current_position: float | None = None, current_text: str | None = None, intent: str | None = None, limit: int = 8) -> list[RetrievedChunk]:
        with self._lock:
            loaded = self._load(work_id)
        if loaded is None:
            raise ValueError("semantic_index_not_preprocessed")
        _, indexed = loaded
        query_vector = self._embeddings.embed_query(query)
        permitted = [item for item in indexed if item.chunk.kind in allowed_kinds]
        ranked = sorted(((item, _score(item, query_vector, current_interval_id, entity_hints, mode=mode, current_position=current_position, current_text=current_text, intent=intent)) for item in permitted), key=lambda item: item[1], reverse=True)
        selected = _diverse_scored(ranked, limit)
        return [RetrievedChunk(item.chunk, score) for item, score in selected]

    def expand_with_scores(self, work_id: str, query: str, *, current_interval_id: str, seed_chunks: list[RetrievedChunk], allowed_kinds: tuple[str, ...], entity_hints: tuple[str, ...] = (), mode: str = "movie", current_position: float | None = None, current_text: str | None = None, intent: str | None = None, radius: int = 1, limit: int = 12) -> list[RetrievedChunk]:
        with self._lock:
            loaded = self._load(work_id)
        if loaded is None:
            raise ValueError("semantic_index_not_preprocessed")
        _, indexed = loaded
        query_vector = self._embeddings.embed_query(query)
        permitted_kinds = set(allowed_kinds) | {"subtitle", "ocr", "dialogue", "paragraph", "glossary"}
        seed_times = [item.chunk.start_time for item in seed_chunks]
        seed_sources = {item.chunk.source for item in seed_chunks}
        candidates = [item for item in indexed if item.chunk.kind in permitted_kinds and _near_seed(item.chunk, seed_times, seed_sources, radius)]
        ranked = sorted(((item, _score(item, query_vector, current_interval_id, entity_hints, mode=mode, current_position=current_position, current_text=current_text, intent=intent)) for item in candidates), key=lambda item: item[1], reverse=True)
        merged = {item.chunk.id: item for item in seed_chunks}
        for item, score in _diverse_scored(ranked, limit):
            merged.setdefault(item.chunk.id, RetrievedChunk(item.chunk, score))
        return sorted(merged.values(), key=lambda item: item.similarity_score, reverse=True)[:limit]

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
        if state.sourceContext and state.sourceContext.subtitle:
            _append(chunks, "subtitle", state.sourceContext.subtitle, "subtitle", base, maximum)
        if state.sourceContext and state.sourceContext.mode == "book" and state.sourceContext.visible_text:
            _append(chunks, "ocr", state.sourceContext.visible_text, "ocr", base, maximum)
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


def _score(item: IndexedChunk, query: tuple[float, ...], current_id: str, entity_hints: tuple[str, ...], *, mode: str, current_position: float | None, current_text: str | None, intent: str | None) -> float:
    semantic = sum(left * right for left, right in zip(item.vector, query, strict=True))
    current_bonus = .20 if item.chunk.interval_id == current_id else 0.0
    entity_bonus = .14 if any(hint.casefold() in {entity.casefold() for entity in item.chunk.entities} for hint in entity_hints) else 0.0
    source_tokens = _tokens(current_text or "")
    source_bonus = .12 if source_tokens and _tokens(item.chunk.text).intersection(source_tokens) else 0.0
    position_bonus = _position_bonus(item.chunk, mode, current_position)
    evidence_bonus = .08 if intent == "definition" and item.chunk.kind in {"subtitle", "dialogue", "glossary", "paragraph", "lore"} else 0.0
    return semantic + current_bonus + entity_bonus + source_bonus + position_bonus + evidence_bonus


def _position_bonus(chunk: SemanticChunk, mode: str, current_position: float | None) -> float:
    if current_position is None:
        return 0.0
    distance = abs(chunk.start_time - current_position)
    if mode == "book":
        # Pages adjacent to the visible page offer useful local context without
        # taking precedence over semantically stronger book-wide evidence.
        return max(0.0, .12 - (.04 * distance))
    # Movie timestamps use a gentle decay so the current subtitles and on-screen
    # evidence are favored while prior causes remain retrievable.
    return max(0.0, .12 - (.001 * distance))


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in value.split() if len(token) > 2}


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


def _diverse_scored(indexed: list[tuple[IndexedChunk, float]], limit: int) -> list[tuple[IndexedChunk, float]]:
    selected: list[tuple[IndexedChunk, float]] = []
    seen: set[tuple[str, str]] = set()
    for item, score in indexed:
        key = (item.chunk.interval_id, item.chunk.kind)
        if key in seen:
            continue
        seen.add(key)
        selected.append((item, score))
        if len(selected) == limit:
            return selected
    return selected


def _fingerprint(chunks: list[SemanticChunk]) -> str:
    return sha256(json.dumps([asdict(chunk) for chunk in chunks], sort_keys=True).encode("utf-8")).hexdigest()


def _near_seed(chunk: SemanticChunk, seed_times: list[float], seed_sources: set[str], radius: int) -> bool:
    if chunk.source in seed_sources:
        return True
    window = 2 * radius if chunk.source.startswith("page:") else 90 * radius
    return any(abs(chunk.start_time - value) <= window for value in seed_times)
