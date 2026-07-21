"""Ports for movie preprocessing infrastructure and external providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from schemas.movie_pipeline import (
    CanonicalMagiFabScene,
    ChunkRecord,
    GeminiVisualScene,
    MovieProcessingStatus,
    MovieRecord,
    SceneRecord,
    SearchContext,
    SearchResult,
)


class MoviePipelineRepository(ABC):
    @abstractmethod
    def find_movie_by_hash(self, content_hash: str) -> MovieRecord | None: ...

    @abstractmethod
    def get_movie(self, movie_id: str) -> MovieRecord | None: ...

    @abstractmethod
    def create_movie(self, *, content_hash: str, title: str | None, original_filename: str, mime_type: str, source_storage_key: str, model_versions: dict[str, str]) -> MovieRecord: ...

    @abstractmethod
    def set_movie_status(self, movie_id: str, status: MovieProcessingStatus, error_message: str | None = None) -> MovieRecord: ...

    @abstractmethod
    def try_start_movie(self, movie_id: str) -> bool: ...

    @abstractmethod
    def list_chunks(self, movie_id: str) -> list[ChunkRecord]: ...

    @abstractmethod
    def replace_chunks(self, movie_id: str, chunks: list[ChunkRecord]) -> list[ChunkRecord]: ...

    @abstractmethod
    def update_chunk(self, chunk_id: str, **changes: object) -> ChunkRecord: ...

    @abstractmethod
    def save_search_context(self, movie_id: str, chunk_id: str, contexts: list[SearchContext]) -> None: ...

    @abstractmethod
    def get_search_context(self, chunk_id: str) -> list[SearchContext]: ...

    @abstractmethod
    def save_scene(self, movie_id: str, chunk_id: str, scene: CanonicalMagiFabScene, model_versions: dict[str, str]) -> SceneRecord: ...

    @abstractmethod
    def list_scenes(self, movie_id: str) -> list[SceneRecord]: ...

    @abstractmethod
    def record_attempt(self, movie_id: str, chunk_id: str | None, stage: str, attempt: int, status: str, error_message: str | None = None) -> None: ...

    @abstractmethod
    def set_progress(self, movie_id: str, stage: str, percentage: int) -> None: ...

    @abstractmethod
    def progress(self, movie_id: str) -> tuple[str, int]: ...


class MovieBlobStorage(ABC):
    @abstractmethod
    def persist_source(self, movie_id: str, temporary_file: Path, filename: str) -> str: ...

    @abstractmethod
    def source_path(self, storage_key: str) -> Path: ...

    @abstractmethod
    def chunk_path(self, movie_id: str, sequence_number: int) -> Path: ...

    @abstractmethod
    def path_for_key(self, storage_key: str) -> Path: ...

    @abstractmethod
    def storage_key(self, path: Path) -> str: ...


class VideoChunker(ABC):
    @abstractmethod
    def split(self, movie_id: str, source_path: Path, chunk_duration_seconds: int) -> list[tuple[float, float, Path]]:
        """Return `(start, end, local_path)` for approximately equal temporal chunks."""


class VideoVisualProvider(ABC):
    @abstractmethod
    def analyze(self, video_path: Path, *, start_seconds: float, end_seconds: float) -> GeminiVisualScene: ...


class SearchProvider(ABC):
    @abstractmethod
    def search(self, query: str) -> list[SearchResult]: ...


class SceneReasoningProvider(ABC):
    @abstractmethod
    def reason(self, visual_scene: GeminiVisualScene, search_context: list[SearchContext], profile: dict[str, object] | None = None) -> CanonicalMagiFabScene: ...
