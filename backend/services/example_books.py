"""Bundled example-book discovery and path resolution helpers."""
from __future__ import annotations

from pathlib import Path
import re


_ALLOWED_SUFFIXES = {".pdf", ".epub", ".txt"}


def get_bundled_example_directories() -> list[Path]:
    backend_root = Path(__file__).resolve().parents[1]
    return [backend_root / "assets" / "books", backend_root / "books"]


def discover_example_books() -> dict[str, Path]:
    discovered: dict[str, Path] = {}
    for directory in get_bundled_example_directories():
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.suffix.lower() not in _ALLOWED_SUFFIXES:
                continue
            file_key = _slug(path.stem)
            discovered.setdefault(file_key, path.resolve())
    return discovered


def get_example_book_path(book_name: str) -> Path:
    key = _slug(book_name)
    discovered = discover_example_books()
    if key in discovered:
        resolved = discovered[key]
        if resolved.is_file():
            return resolved
        raise FileNotFoundError(f"Example '{book_name}' resolved to '{resolved}', but the file does not exist.")

    searched = ", ".join(str(path.resolve()) for path in get_bundled_example_directories())
    available = ", ".join(sorted(discovered)) or "none"
    raise FileNotFoundError(
        f"Example '{book_name}' was not found. Searched directories: {searched}. Available examples: {available}."
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
