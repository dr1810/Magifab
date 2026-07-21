"""Local durable implementations for movie artifacts and preprocessing records.

SQLite is intentionally only the development implementation. The repository
contract maps directly to the Supabase migration and keeps pipeline services
free of SQL, object-store, and provider details.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4

from models.movie_pipeline import MovieBlobStorage, MoviePipelineRepository
from schemas.movie_pipeline import (
    CanonicalMagiFabScene,
    ChunkRecord,
    ChunkProcessingStatus,
    GeminiVisualScene,
    MovieProcessingStatus,
    MovieRecord,
    SceneRecord,
    SearchContext,
)


class LocalMovieBlobStorage(MovieBlobStorage):
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def persist_source(self, movie_id: str, temporary_file: Path, filename: str) -> str:
        safe_name = Path(filename).name or "movie.mp4"
        relative = Path("sources") / movie_id / safe_name
        target = self._root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(temporary_file, target)
        return relative.as_posix()

    def source_path(self, storage_key: str) -> Path:
        return self.path_for_key(storage_key)

    def chunk_path(self, movie_id: str, sequence_number: int) -> Path:
        target = self._root / "chunks" / movie_id / f"chunk-{sequence_number:05d}.mp4"
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def path_for_key(self, storage_key: str) -> Path:
        target = (self._root / storage_key).resolve()
        if self._root != target and self._root not in target.parents:
            raise ValueError("invalid_movie_storage_key")
        return target

    def storage_key(self, path: Path) -> str:
        return path.resolve().relative_to(self._root).as_posix()


class SqliteMoviePipelineRepository(MoviePipelineRepository):
    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self._database = root / "movie_pipeline.sqlite3"
        self._create_tables()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _create_tables(self) -> None:
        with self._connect() as db:
            db.executescript("""
                create table if not exists movies (
                    id text primary key, content_hash text not null unique, title text,
                    original_filename text not null, mime_type text not null,
                    source_storage_key text not null, status text not null,
                    model_versions text not null, error_message text,
                    created_at text not null, updated_at text not null
                );
                create table if not exists chunks (
                    id text primary key, movie_id text not null references movies(id) on delete cascade,
                    sequence_number integer not null, start_seconds real not null, end_seconds real not null,
                    duration_seconds real not null, content_hash text not null, storage_key text not null,
                    status text not null, model_versions text not null, gemini_visual_json text,
                    error_message text, created_at text not null, updated_at text not null,
                    unique(movie_id, sequence_number)
                );
                create table if not exists scenes (
                    id text primary key, movie_id text not null references movies(id) on delete cascade,
                    chunk_id text not null unique references chunks(id) on delete cascade,
                    canonical_json text not null, confidence text not null, model_versions text not null,
                    created_at text not null, updated_at text not null
                );
                create table if not exists search_context (
                    id text primary key, movie_id text not null references movies(id) on delete cascade,
                    chunk_id text not null references chunks(id) on delete cascade,
                    entity text not null, entity_kind text not null, query text not null,
                    results_json text not null, confidence real not null, created_at text not null
                );
                create table if not exists processing_attempts (
                    id text primary key, movie_id text not null references movies(id) on delete cascade,
                    chunk_id text references chunks(id) on delete cascade, stage text not null,
                    attempt integer not null, status text not null, error_message text, created_at text not null
                );
                create index if not exists chunks_movie_time_idx on chunks(movie_id, start_seconds);
                create index if not exists search_context_chunk_idx on search_context(chunk_id);
            """)

    def find_movie_by_hash(self, content_hash: str) -> MovieRecord | None:
        with self._connect() as db:
            row = db.execute("select * from movies where content_hash = ?", (content_hash,)).fetchone()
        return _movie(row) if row else None

    def get_movie(self, movie_id: str) -> MovieRecord | None:
        with self._connect() as db:
            row = db.execute("select * from movies where id = ?", (movie_id,)).fetchone()
        return _movie(row) if row else None

    def create_movie(self, *, content_hash: str, title: str | None, original_filename: str, mime_type: str, source_storage_key: str, model_versions: dict[str, str]) -> MovieRecord:
        now = _now()
        movie_id = str(uuid4())
        with self._connect() as db:
            try:
                db.execute("insert into movies values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                    movie_id, content_hash, title, original_filename, mime_type, source_storage_key,
                    MovieProcessingStatus.UPLOADED.value, _dump(model_versions), None, now, now,
                ))
            except sqlite3.IntegrityError:
                row = db.execute("select * from movies where content_hash = ?", (content_hash,)).fetchone()
                if row:
                    return _movie(row)
                raise
        movie = self.get_movie(movie_id)
        assert movie is not None
        return movie

    def set_movie_status(self, movie_id: str, status: MovieProcessingStatus, error_message: str | None = None) -> MovieRecord:
        with self._connect() as db:
            db.execute("update movies set status = ?, error_message = ?, updated_at = ? where id = ?", (status.value, error_message, _now(), movie_id))
        movie = self.get_movie(movie_id)
        if movie is None:
            raise KeyError("movie_not_found")
        return movie

    def try_start_movie(self, movie_id: str) -> bool:
        with self._connect() as db:
            changed = db.execute("""update movies set status = ?, error_message = null, updated_at = ?
                where id = ? and status not in (?, ?)""", (
                MovieProcessingStatus.PROCESSING.value, _now(), movie_id,
                MovieProcessingStatus.PROCESSING.value, MovieProcessingStatus.COMPLETED.value,
            )).rowcount
        return changed == 1

    def list_chunks(self, movie_id: str) -> list[ChunkRecord]:
        with self._connect() as db:
            rows = db.execute("select * from chunks where movie_id = ? order by sequence_number", (movie_id,)).fetchall()
        return [_chunk(row) for row in rows]

    def replace_chunks(self, movie_id: str, chunks: list[ChunkRecord]) -> list[ChunkRecord]:
        with self._connect() as db:
            existing = db.execute("select count(*) from chunks where movie_id = ?", (movie_id,)).fetchone()[0]
            if existing:
                return self.list_chunks(movie_id)
            db.executemany("insert into chunks values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
                (chunk.id, chunk.movie_id, chunk.sequence_number, chunk.start_seconds, chunk.end_seconds,
                 chunk.duration_seconds, chunk.content_hash, chunk.storage_key, chunk.status.value,
                 _dump(chunk.model_versions), _dump(chunk.gemini_visual_json.model_dump(mode="json")) if chunk.gemini_visual_json else None,
                 chunk.error_message, _iso(chunk.created_at), _iso(chunk.updated_at))
                for chunk in chunks
            ])
        return self.list_chunks(movie_id)

    def update_chunk(self, chunk_id: str, **changes: object) -> ChunkRecord:
        allowed = {"status", "model_versions", "gemini_visual_json", "error_message"}
        assignments: list[str] = []
        values: list[object] = []
        for key, value in changes.items():
            if key not in allowed:
                raise ValueError(f"unsupported_chunk_change:{key}")
            assignments.append(f"{key} = ?")
            if key == "status" and isinstance(value, ChunkProcessingStatus):
                values.append(value.value)
            elif key == "model_versions":
                values.append(_dump(value))
            elif key == "gemini_visual_json":
                values.append(_dump(value.model_dump(mode="json")) if isinstance(value, GeminiVisualScene) else None)
            else:
                values.append(value)
        assignments.append("updated_at = ?")
        values.extend([_now(), chunk_id])
        with self._connect() as db:
            db.execute(f"update chunks set {', '.join(assignments)} where id = ?", values)
            row = db.execute("select * from chunks where id = ?", (chunk_id,)).fetchone()
        if row is None:
            raise KeyError("chunk_not_found")
        return _chunk(row)

    def save_search_context(self, movie_id: str, chunk_id: str, contexts: list[SearchContext]) -> None:
        with self._connect() as db:
            db.execute("delete from search_context where chunk_id = ?", (chunk_id,))
            db.executemany("insert into search_context values (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
                (str(uuid4()), movie_id, chunk_id, item.entity, item.entity_kind, item.query,
                 _dump([result.model_dump(mode="json") for result in item.results]), item.confidence, _now())
                for item in contexts
            ])

    def get_search_context(self, chunk_id: str) -> list[SearchContext]:
        with self._connect() as db:
            rows = db.execute("select * from search_context where chunk_id = ? order by created_at, id", (chunk_id,)).fetchall()
        return [SearchContext(entity=row["entity"], entity_kind=row["entity_kind"], query=row["query"], results=json.loads(row["results_json"]), confidence=row["confidence"]) for row in rows]

    def save_scene(self, movie_id: str, chunk_id: str, scene: CanonicalMagiFabScene, model_versions: dict[str, str]) -> SceneRecord:
        now = _now()
        with self._connect() as db:
            previous = db.execute("select id, created_at from scenes where chunk_id = ?", (chunk_id,)).fetchone()
            scene_id = previous["id"] if previous else str(uuid4())
            created_at = previous["created_at"] if previous else now
            db.execute("""insert into scenes values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(chunk_id) do update set canonical_json = excluded.canonical_json,
                confidence = excluded.confidence, model_versions = excluded.model_versions, updated_at = excluded.updated_at""",
                (scene_id, movie_id, chunk_id, _dump(scene.model_dump(mode="json")), scene.confidence.value, _dump(model_versions), created_at, now))
            row = db.execute("select * from scenes where chunk_id = ?", (chunk_id,)).fetchone()
        assert row is not None
        return _scene(row)

    def list_scenes(self, movie_id: str) -> list[SceneRecord]:
        with self._connect() as db:
            rows = db.execute("""select scenes.* from scenes join chunks on chunks.id = scenes.chunk_id
                where scenes.movie_id = ? order by chunks.start_seconds""", (movie_id,)).fetchall()
        return [_scene(row) for row in rows]

    def record_attempt(self, movie_id: str, chunk_id: str | None, stage: str, attempt: int, status: str, error_message: str | None = None) -> None:
        with self._connect() as db:
            db.execute("insert into processing_attempts values (?, ?, ?, ?, ?, ?, ?, ?)", (str(uuid4()), movie_id, chunk_id, stage, attempt, status, error_message, _now()))


def _movie(row: sqlite3.Row) -> MovieRecord:
    data = dict(row)
    data["model_versions"] = json.loads(row["model_versions"])
    return MovieRecord(**data)


def _chunk(row: sqlite3.Row) -> ChunkRecord:
    data = dict(row)
    data["model_versions"] = json.loads(row["model_versions"])
    data["gemini_visual_json"] = json.loads(row["gemini_visual_json"]) if row["gemini_visual_json"] else None
    return ChunkRecord(**data)


def _scene(row: sqlite3.Row) -> SceneRecord:
    return SceneRecord(id=row["id"], movie_id=row["movie_id"], chunk_id=row["chunk_id"], canonical_scene=json.loads(row["canonical_json"]), model_versions=json.loads(row["model_versions"]), created_at=row["created_at"], updated_at=row["updated_at"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat() if value.tzinfo else value.replace(tzinfo=timezone.utc).isoformat()


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
