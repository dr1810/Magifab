"""Orchestrates one-time movie preprocessing without coupling to a vendor or database."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from pathlib import Path
from typing import Callable, TypeVar
from uuid import uuid4

from models.movie_pipeline import MovieBlobStorage, MoviePipelineRepository, SceneReasoningProvider, SearchProvider, VideoChunker, VideoVisualProvider
from schemas.movie_pipeline import (
    ChunkProcessingStatus,
    ChunkRecord,
    MoviePreprocessResponse,
    MovieProcessingStatus,
    MovieProcessingStatusResponse,
    MovieRecord,
    MovieUploadResponse,
    SearchContext,
    SceneLookupResponse,
)
from services.movie_pipeline_retry import RetryExecutor
from services.search_query_planner import SearchQueryPlanner


logger = logging.getLogger(__name__)
T = TypeVar("T")


class MoviePipelineService:
    def __init__(
        self,
        *,
        repository: MoviePipelineRepository,
        blobs: MovieBlobStorage,
        chunker: VideoChunker,
        visual_provider: VideoVisualProvider,
        search_provider: SearchProvider,
        reasoning_provider: SceneReasoningProvider,
        chunk_duration_seconds: int,
        retry_executor: RetryExecutor,
        model_versions: dict[str, str],
        query_planner: SearchQueryPlanner | None = None,
    ) -> None:
        self._repository = repository
        self._blobs = blobs
        self._chunker = chunker
        self._visual_provider = visual_provider
        self._search_provider = search_provider
        self._reasoning_provider = reasoning_provider
        self._chunk_duration_seconds = chunk_duration_seconds
        self._retry = retry_executor
        self._model_versions = model_versions
        self._query_planner = query_planner or SearchQueryPlanner()

    def upload(self, temporary_file: Path, filename: str, mime_type: str, title: str | None = None) -> MovieUploadResponse:
        content_hash = file_sha256(temporary_file)
        existing = self._repository.find_movie_by_hash(content_hash)
        if existing:
            _log("movie_upload", outcome="cache_hit", movie_id=existing.id, content_hash=content_hash)
            return MovieUploadResponse(movie_id=existing.id, content_hash=content_hash, status=existing.status, reused_existing=True)
        storage_key = self._blobs.persist_source(content_hash, temporary_file, filename)
        movie = self._repository.create_movie(
            content_hash=content_hash, title=title.strip() if title and title.strip() else None,
            original_filename=Path(filename).name or "movie",
            mime_type=mime_type or "video/mp4",
            source_storage_key=storage_key,
            model_versions=self._model_versions,
        )
        # A competing upload can win the hash unique constraint after the initial lookup.
        _log("movie_upload", outcome="cache_miss", movie_id=movie.id, content_hash=content_hash)
        return MovieUploadResponse(movie_id=movie.id, content_hash=content_hash, status=movie.status, reused_existing=False)

    def start(self, movie_id: str) -> MoviePreprocessResponse:
        movie = self._require_movie(movie_id)
        if movie.status == MovieProcessingStatus.COMPLETED:
            _log("preprocessing_start", outcome="already_completed", movie_id=movie_id)
            return MoviePreprocessResponse(movie_id=movie_id, status=movie.status, accepted=False)
        accepted = self._repository.try_start_movie(movie_id)
        status = MovieProcessingStatus.PROCESSING if accepted else self._require_movie(movie_id).status
        _log("preprocessing_start", outcome="accepted" if accepted else "already_processing", movie_id=movie_id)
        return MoviePreprocessResponse(movie_id=movie_id, status=status, accepted=accepted)

    def preprocess(self, movie_id: str) -> None:
        movie = self._require_movie(movie_id)
        if movie.status == MovieProcessingStatus.COMPLETED:
            return
        try:
            chunks = self._chunks_for(movie)
        except Exception as error:
            self._repository.set_movie_status(movie_id, MovieProcessingStatus.FAILED, str(error))
            _log("chunk_creation", outcome="failed", movie_id=movie_id, error=str(error))
            return
        failures = 0
        for chunk in chunks:
            if chunk.status == ChunkProcessingStatus.COMPLETED:
                continue
            try:
                self._process_chunk(movie, chunk)
            except Exception as error:
                failures += 1
                self._repository.update_chunk(chunk.id, status=ChunkProcessingStatus.FAILED, error_message=str(error), model_versions=self._model_versions)
                _log("chunk_processing", outcome="failed", movie_id=movie.id, chunk_id=chunk.id, error=str(error))
        final_chunks = self._repository.list_chunks(movie_id)
        if final_chunks and all(chunk.status == ChunkProcessingStatus.COMPLETED for chunk in final_chunks):
            final_status = MovieProcessingStatus.COMPLETED
        elif any(chunk.status == ChunkProcessingStatus.COMPLETED for chunk in final_chunks):
            final_status = MovieProcessingStatus.PARTIAL
        else:
            final_status = MovieProcessingStatus.FAILED
        self._repository.set_movie_status(movie_id, final_status, None if final_status == MovieProcessingStatus.COMPLETED else f"{failures or len(final_chunks)} chunk(s) require retry")
        _log("preprocessing_completion", movie_id=movie_id, status=final_status.value, chunks=len(final_chunks), failures=failures)

    def status(self, movie_id: str) -> MovieProcessingStatusResponse:
        movie = self._require_movie(movie_id)
        counts: dict[str, int] = {status.value: 0 for status in ChunkProcessingStatus}
        for chunk in self._repository.list_chunks(movie_id):
            counts[chunk.status.value] += 1
        return MovieProcessingStatusResponse(movie=movie, chunk_counts=counts)

    def chunks(self, movie_id: str) -> list[ChunkRecord]:
        self._require_movie(movie_id)
        return self._repository.list_chunks(movie_id)

    def movie(self, movie_id: str) -> MovieRecord:
        return self._require_movie(movie_id)

    def scene_at(self, movie_id: str, timestamp: float) -> SceneLookupResponse:
        self._require_movie(movie_id)
        chunks = self._repository.list_chunks(movie_id)
        chunk = next((item for item in chunks if item.start_seconds <= timestamp < item.end_seconds), None)
        if chunk is None and chunks and timestamp >= chunks[-1].end_seconds:
            chunk = chunks[-1]
        if chunk is None:
            return SceneLookupResponse()
        scene = next((item for item in self._repository.list_scenes(movie_id) if item.chunk_id == chunk.id), None)
        return SceneLookupResponse(scene=scene, chunk=chunk)

    def source_path(self, movie_id: str) -> Path:
        movie = self._require_movie(movie_id)
        path = self._blobs.source_path(movie.source_storage_key)
        if not path.is_file():
            raise FileNotFoundError("movie_source_blob_not_found")
        return path

    def scenes(self, movie_id: str):
        self._require_movie(movie_id)
        return self._repository.list_scenes(movie_id)

    def _chunks_for(self, movie: MovieRecord) -> list[ChunkRecord]:
        existing = self._repository.list_chunks(movie.id)
        if existing:
            return existing
        source_path = self._blobs.source_path(movie.source_storage_key)
        if not source_path.exists():
            raise FileNotFoundError("movie_source_blob_not_found")
        paths = self._run_stage(movie.id, None, "chunking", lambda: self._chunker.split(movie.id, source_path, self._chunk_duration_seconds))
        now = datetime.now(timezone.utc)
        chunks: list[ChunkRecord] = []
        for sequence, (start, end, path) in enumerate(paths):
            chunks.append(ChunkRecord(
                id=str(uuid4()), movie_id=movie.id, sequence_number=sequence,
                start_seconds=start, end_seconds=end, duration_seconds=end - start,
                content_hash=file_sha256(path), storage_key=self._blobs.storage_key(path),
                status=ChunkProcessingStatus.PENDING, model_versions=self._model_versions,
                created_at=now, updated_at=now,
            ))
        if not chunks:
            raise RuntimeError("video_produced_no_chunks")
        stored = self._repository.replace_chunks(movie.id, chunks)
        _log("chunk_creation", outcome="succeeded", movie_id=movie.id, chunks=len(stored))
        return stored

    def _process_chunk(self, movie: MovieRecord, chunk: ChunkRecord) -> None:
        self._repository.update_chunk(chunk.id, status=ChunkProcessingStatus.PROCESSING, error_message=None, model_versions=self._model_versions)
        path = self._blobs.path_for_key(chunk.storage_key)
        visual = self._run_stage(movie.id, chunk.id, "gemini", lambda: self._visual_provider.analyze(path, start_seconds=chunk.start_seconds, end_seconds=chunk.end_seconds))
        self._repository.update_chunk(chunk.id, gemini_visual_json=visual, model_versions=self._model_versions)
        _log("gemini_processing", outcome="succeeded", movie_id=movie.id, chunk_id=chunk.id, model=self._model_versions.get("gemini"))
        contexts: list[SearchContext] = []
        for entity, query in self._query_planner.build(visual, movie.title):
            results = self._run_stage(movie.id, chunk.id, "google_search", lambda query=query: self._search_provider.search(query))
            contexts.append(SearchContext(entity=entity.entity, entity_kind=entity.kind, query=query, results=results, confidence=max((item.confidence for item in results), default=0.0)))
        self._repository.save_search_context(movie.id, chunk.id, contexts)
        _log("search_enrichment", outcome="succeeded", movie_id=movie.id, chunk_id=chunk.id, queries=len(contexts))
        canonical = self._run_stage(movie.id, chunk.id, "openai", lambda: self._reasoning_provider.reason(visual, contexts))
        canonical = canonical.model_copy(update={"search_context": contexts})
        self._repository.save_scene(movie.id, chunk.id, canonical, self._model_versions)
        self._repository.update_chunk(chunk.id, status=ChunkProcessingStatus.COMPLETED, error_message=None, model_versions=self._model_versions)
        _log("openai_reasoning", outcome="succeeded", movie_id=movie.id, chunk_id=chunk.id, model=self._model_versions.get("openai"))

    def _run_stage(self, movie_id: str, chunk_id: str | None, stage: str, action: Callable[[], T]) -> T:
        def audit(attempt: int, status: str, error: Exception | None) -> None:
            self._repository.record_attempt(movie_id, chunk_id, stage, attempt, status, str(error) if error else None)
            _log(stage, movie_id=movie_id, chunk_id=chunk_id, attempt=attempt, outcome=status, error=str(error) if error else None)
        return self._retry.run(action, on_attempt=audit)

    def _require_movie(self, movie_id: str) -> MovieRecord:
        movie = self._repository.get_movie(movie_id)
        if movie is None:
            raise KeyError("movie_not_found")
        return movie


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _log(event: str, **fields: object) -> None:
    logger.info(json.dumps({"event": event, **{key: value for key, value in fields.items() if value is not None}}, default=str, sort_keys=True))
