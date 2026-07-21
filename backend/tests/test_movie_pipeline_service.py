from datetime import datetime, timezone
from pathlib import Path

from models.movie_pipeline import SceneReasoningProvider, SearchProvider, VideoChunker, VideoVisualProvider
from schemas.movie_pipeline import (
    CanonicalMagiFabScene,
    Confidence,
    EntityNeedingIdentification,
    GeminiVisualScene,
    SearchResult,
    VisualAid,
)
from services.movie_pipeline_retry import RetryExecutor
from services.movie_pipeline_service import MoviePipelineService
from services.movie_pipeline_storage import LocalMovieBlobStorage, SqliteMoviePipelineRepository


class FakeChunker(VideoChunker):
    def __init__(self, count: int = 1) -> None:
        self.count = count

    def split(self, movie_id: str, source_path: Path, chunk_duration_seconds: int):
        chunks = []
        for sequence in range(self.count):
            target = source_path.parent.parent.parent / "chunks" / movie_id / f"chunk-{sequence:05d}.mp4"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(f"chunk-{sequence}".encode())
            chunks.append((float(sequence * 90), float((sequence + 1) * 90), target))
        return chunks


class FakeVisual(VideoVisualProvider):
    def __init__(self, fail_second: bool = False) -> None:
        self.calls = 0
        self.fail_second = fail_second

    def analyze(self, video_path: Path, *, start_seconds: float, end_seconds: float) -> GeminiVisualScene:
        self.calls += 1
        if self.fail_second and self.calls == 2:
            raise RuntimeError("simulated Gemini outage")
        return GeminiVisualScene(
            scene_summary="An unknown figure holds a marked book.",
            entities_needing_identification=[EntityNeedingIdentification(entity="Unknown", kind="character", description="a figure wearing a distinctive silver mask", reason="face is not visually identifiable", certainty=Confidence.LOW)],
            confidence=Confidence.LOW,
        )


class FakeSearch(SearchProvider):
    def __init__(self) -> None:
        self.calls = 0

    def search(self, query: str):
        self.calls += 1
        return [SearchResult(title="Evidence", snippet="Grounded result", url="https://example.test/evidence", confidence=0.8)]


class FakeReasoner(SceneReasoningProvider):
    def __init__(self) -> None:
        self.calls = 0

    def reason(self, visual_scene, search_context):
        self.calls += 1
        return CanonicalMagiFabScene(
            scene_summary=visual_scene.scene_summary,
            visual_aid=VisualAid(type="object-card", description="Show the marked book."),
            accessibility_explanation="The figure is holding a book. Their identity is still unknown.",
            confidence=Confidence.LOW,
        )


def _service(tmp_path: Path, *, chunks: int = 1, fail_second: bool = False):
    storage = LocalMovieBlobStorage(tmp_path / "pipeline")
    visual, search, reasoner = FakeVisual(fail_second), FakeSearch(), FakeReasoner()
    service = MoviePipelineService(
        repository=SqliteMoviePipelineRepository(tmp_path / "pipeline"), blobs=storage,
        chunker=FakeChunker(chunks), visual_provider=visual, search_provider=search,
        reasoning_provider=reasoner, chunk_duration_seconds=90,
        retry_executor=RetryExecutor(1, 0.001), model_versions={"gemini": "test-gemini", "openai": "test-openai"},
    )
    return service, visual, search, reasoner


def test_identical_upload_reuses_movie_and_completed_scenes_without_provider_calls(tmp_path):
    service, visual, search, reasoner = _service(tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"same movie")
    first = service.upload(source, "movie.mp4", "video/mp4", "Example")
    assert first.reused_existing is False
    assert service.start(first.movie_id).accepted is True
    service.preprocess(first.movie_id)
    assert service.status(first.movie_id).movie.status == "completed"
    assert len(service.scenes(first.movie_id)) == 1
    calls = (visual.calls, search.calls, reasoner.calls)

    duplicate = service.upload(source, "copy.mp4", "video/mp4", "Example")
    assert duplicate.reused_existing is True
    assert duplicate.movie_id == first.movie_id
    assert service.start(duplicate.movie_id).accepted is False
    assert (visual.calls, search.calls, reasoner.calls) == calls


def test_failed_chunk_does_not_stop_later_chunks_and_movie_is_partial(tmp_path):
    service, visual, search, reasoner = _service(tmp_path, chunks=2, fail_second=True)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"two chunks")
    movie = service.upload(source, "movie.mp4", "video/mp4")
    assert service.start(movie.movie_id).accepted
    service.preprocess(movie.movie_id)

    status = service.status(movie.movie_id)
    assert status.movie.status == "partial"
    assert status.chunk_counts == {"pending": 0, "processing": 0, "completed": 1, "failed": 1}
    assert len(service.scenes(movie.movie_id)) == 1
    assert search.calls == 1
    assert reasoner.calls == 1
