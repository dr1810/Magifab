"""Evidence-driven Google Search query planning with a strict generic-entity denylist."""
from __future__ import annotations

import re

from schemas.movie_pipeline import EntityNeedingIdentification, GeminiVisualScene


_SEARCHABLE_KINDS = {
    "unknown character", "character", "creature", "landmark", "movie title",
    "text", "object with text", "organization", "book", "historical person",
}
_GENERIC_WORDS = {"tree", "forest", "grass", "walking", "clothes", "red object", "person", "animal"}


class SearchQueryPlanner:
    def build(self, visual_scene: GeminiVisualScene, movie_title: str | None) -> list[tuple[EntityNeedingIdentification, str]]:
        planned: list[tuple[EntityNeedingIdentification, str]] = []
        seen: set[str] = set()
        for entity in visual_scene.entities_needing_identification:
            kind = _normalise(entity.kind)
            description = " ".join(entity.description.split())
            if kind not in _SEARCHABLE_KINDS or not description or _is_generic(description):
                continue
            context = f' in the film "{movie_title}"' if movie_title else " in a movie scene"
            query = _query(kind, entity.entity, description, context)
            key = query.casefold()
            if key not in seen:
                planned.append((entity, query))
                seen.add(key)
        return planned[:4]


def _query(kind: str, entity: str, description: str, context: str) -> str:
    if kind == "movie title":
        return f"identify movie title from {description}"
    if kind in {"text", "object with text"}:
        return f"identify text or organization shown on {description}{context}"
    if kind == "historical person":
        return f"identify historical person matching {description}"
    return f"identify {kind} matching {description}{context}"


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def _is_generic(description: str) -> bool:
    compact = _normalise(description)
    return compact in _GENERIC_WORDS or all(word in _GENERIC_WORDS for word in re.findall(r"[a-z]+", compact))
