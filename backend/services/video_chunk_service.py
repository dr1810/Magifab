"""Video duration probing and approximately 90-second MP4 chunk generation."""
from __future__ import annotations

from pathlib import Path
import json
import subprocess

from models.movie_pipeline import VideoChunker
from services.movie_pipeline_storage import LocalMovieBlobStorage


class FfmpegVideoChunker(VideoChunker):
    def __init__(self, storage: LocalMovieBlobStorage) -> None:
        self._storage = storage

    def split(self, movie_id: str, source_path: Path, chunk_duration_seconds: int) -> list[tuple[float, float, Path]]:
        duration = self._duration(source_path)
        if duration <= 0:
            raise ValueError("video_duration_unavailable")
        chunks: list[tuple[float, float, Path]] = []
        start = 0.0
        sequence = 0
        while start < duration:
            end = min(start + chunk_duration_seconds, duration)
            target = self._storage.chunk_path(movie_id, sequence)
            self._run("ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(source_path), "-t", f"{end - start:.3f}", "-map", "0", "-c", "copy", "-movflags", "+faststart", str(target))
            if not target.exists() or target.stat().st_size == 0:
                raise RuntimeError("ffmpeg_created_empty_chunk")
            chunks.append((start, end, target))
            start = end
            sequence += 1
        return chunks

    @staticmethod
    def _duration(source_path: Path) -> float:
        result = FfmpegVideoChunker._run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(source_path))
        try:
            return float(json.loads(result.stdout)["format"]["duration"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("ffprobe_returned_invalid_duration") from error

    @staticmethod
    def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(arguments, check=True, capture_output=True, text=True, timeout=600)
        except FileNotFoundError as error:
            raise RuntimeError("ffmpeg_and_ffprobe_are_required_for_movie_preprocessing") from error
        except subprocess.CalledProcessError as error:
            message = (error.stderr or error.stdout or "ffmpeg failed").strip()[-1_000:]
            raise RuntimeError(f"video_chunking_failed:{message}") from error
