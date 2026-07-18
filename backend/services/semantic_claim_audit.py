"""Consistent semantic-claim pipeline diagnostics.

This module is intentionally read-only: it lets every pipeline boundary prove
that claim IDs and kinds survived without changing semantic facts.
"""
import logging


def log_claims(stage: str, claims, *, movie_id: str | None = None, scene_id: str | None = None) -> None:
    items = list(claims)
    counts = {
        "character": sum(item.kind == "character_present" for item in items),
        "relationship": sum(item.kind == "relationship" for item in items),
        "timeline": sum(item.kind == "timeline_change" for item in items),
        "scene_state": sum(item.kind == "scene_state" for item in items),
    }
    logging.getLogger(__name__).info(
        "[TRACE][SEMANTIC_CLAIMS] stage=%s movie=%s scene=%s semantic_claims=%d "
        "character_claims=%d relationship_claims=%d timeline_claims=%d scene_state_claims=%d claim_ids=%s",
        stage, movie_id, scene_id, len(items), counts["character"], counts["relationship"],
        counts["timeline"], counts["scene_state"], [item.id for item in items],
    )
