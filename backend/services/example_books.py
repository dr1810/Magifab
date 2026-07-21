"""Bundled example-book discovery and path resolution helpers."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil


_ALLOWED_SUFFIXES = {".pdf", ".epub", ".txt"}
BOOKS_DIR = Path(__file__).resolve().parent.parent / "assets" / "books"
LEGACY_BOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "books"


def get_bundled_example_directories() -> list[Path]:
    return [BOOKS_DIR]


def discover_example_books() -> dict[str, Path]:
    _migrate_legacy_books_for_local_dev()
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
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

    # Fuzzy fallback for friendly endpoint names (e.g. "dune") where the
    # bundled filename stem may be longer (e.g. "frank-herbert-dune-1-dune").
    fuzzy_matches = [path for discovered_key, path in discovered.items() if key and key in discovered_key]
    if len(fuzzy_matches) == 1:
        resolved = fuzzy_matches[0]
        if resolved.is_file():
            return resolved
        raise FileNotFoundError(f"Example '{book_name}' matched '{resolved}', but the file does not exist.")
    if len(fuzzy_matches) > 1:
        options = ", ".join(str(path.name) for path in fuzzy_matches)
        raise FileNotFoundError(
            f"Example '{book_name}' is ambiguous. Matching bundled files: {options}. Use /examples/{{exact-name}}."
        )

    searched = ", ".join(str(path.resolve()) for path in get_bundled_example_directories())
    available = ", ".join(sorted(discovered)) or "none"
    raise FileNotFoundError(
        f"Example '{book_name}' was not found. Searched directories: {searched}. Available examples: {available}."
    )


def list_discovered_book_filenames() -> list[str]:
    return sorted(path.name for path in discover_example_books().values())


def has_any_example_books() -> bool:
    return bool(discover_example_books())


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _migrate_legacy_books_for_local_dev() -> None:
    environment = os.getenv("MAGIFAB_ENVIRONMENT", os.getenv("ENVIRONMENT", "development")).casefold()
    if environment in {"production", "prod"}:
        return
    if not LEGACY_BOOKS_DIR.is_dir():
        return

    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    for path in LEGACY_BOOKS_DIR.iterdir():
        if not path.is_file() or path.suffix.lower() not in _ALLOWED_SUFFIXES:
            continue
        destination = BOOKS_DIR / path.name
        if destination.exists():
            continue
        shutil.copy2(path, destination)
