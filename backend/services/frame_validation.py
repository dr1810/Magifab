"""Frame diagnostics and validity checks performed before any AI inference."""
from __future__ import annotations

import math
import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image


class InvalidFrameError(ValueError):
    """A decoded image is syntactically valid but unsuitable for perception."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class FrameDiagnostics:
    width: int
    height: int
    average_pixel: float
    entropy: float
    file_size: int
    black_pixel_ratio: float
    timestamp: float
    image_valid: bool
    reason: str | None = None
    debug_frame: str | None = None


_last_frame: FrameDiagnostics | None = None
_lock = threading.Lock()


def validate_frame(image: Image.Image, *, file_size: int, timestamp: float, debug_dir: Path, scene_id: str) -> FrameDiagnostics:
    """Persist and inspect the exact frame before it can reach a model."""
    grayscale = image.convert("L")
    pixel_count = image.width * image.height
    histogram = grayscale.histogram()
    average_pixel = sum(value * count for value, count in enumerate(histogram)) / pixel_count
    entropy = -sum((count / pixel_count) * math.log2(count / pixel_count) for count in histogram if count)
    black_pixel_ratio = sum(histogram[:13]) / pixel_count
    reason = _invalid_reason(image.width, image.height, file_size, average_pixel, entropy, black_pixel_ratio)
    debug_frame = _save_debug_frame(image, debug_dir, scene_id, timestamp)
    diagnostics = FrameDiagnostics(
        width=image.width,
        height=image.height,
        average_pixel=round(average_pixel, 3),
        entropy=round(entropy, 4),
        file_size=file_size,
        black_pixel_ratio=round(black_pixel_ratio, 4),
        timestamp=timestamp,
        image_valid=reason is None,
        reason=reason,
        debug_frame=debug_frame,
    )
    with _lock:
        global _last_frame
        _last_frame = diagnostics
    if reason:
        raise InvalidFrameError(reason)
    return diagnostics


def latest_frame_diagnostics() -> dict[str, object]:
    """Return the most recent received frame; no image or semantic data is exposed."""
    with _lock:
        return asdict(_last_frame) if _last_frame else {
            "width": 0, "height": 0, "average_pixel": 0.0, "entropy": 0.0,
            "file_size": 0, "black_pixel_ratio": 0.0, "timestamp": 0.0,
            "image_valid": False, "reason": "no_frame_received", "debug_frame": None,
        }


def _invalid_reason(width: int, height: int, file_size: int, average: float, entropy: float, black_ratio: float) -> str | None:
    if width < 64 or height < 64:
        return "frame_dimensions_too_small"
    if file_size < 1024:
        return "frame_file_too_small"
    if average <= 3 or black_ratio >= 0.92:
        return "black_frame_detected"
    # Uniform bright frames and low-information slates are not useful scene
    # evidence even though they are not technically black.
    if average >= 252 and entropy < 0.15:
        return "blank_frame_detected"
    if entropy < 0.15:
        return "title_card_detected"
    return None


def _save_debug_frame(image: Image.Image, debug_dir: Path, scene_id: str, timestamp: float) -> str:
    debug_dir.mkdir(parents=True, exist_ok=True)
    safe_scene_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", scene_id).strip("-") or "scene"
    path = debug_dir / f"{safe_scene_id}-{int(timestamp * 1000):06d}.png"
    image.save(path, format="PNG")
    return str(path)
