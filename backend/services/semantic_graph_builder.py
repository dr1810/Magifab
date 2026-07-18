"""Converts raw observations into provenance-backed semantic movie claims."""
from hashlib import sha256

from schemas.fusion import UnifiedSceneRepresentation
from schemas.knowledge import SemanticMovieKnowledge
from schemas.matching import SemanticMatchResult
from schemas.observation import FrameObservation
from schemas.semantic_graph import SemanticClaim


class SemanticGraphBuilder:
    """The only boundary that may turn perception evidence into semantic assertions."""

    def build(
        self,
        *,
        observation: FrameObservation,
        perception: UnifiedSceneRepresentation,
        matches: SemanticMatchResult,
        existing: SemanticMovieKnowledge,
    ) -> list[SemanticClaim]:
        verified = {match.entity.label.lower(): match.id for match in matches.characters}
        claims: list[SemanticClaim] = []
        prior_labels = {
            claim.subject_id for claim in existing.semantic_claims
            if claim.timestamp_seconds < observation.timestamp_seconds and claim.kind in {"character_present", "object_present"}
        }
        for entity in perception.entities:
            if entity.category not in {"person", "animal", "object"}:
                continue
            semantic_id = verified.get(entity.label.lower()) or _stable_id(entity.category, entity.label)
            kind = "character_present" if entity.category in {"person", "animal"} else "object_present"
            confidence = entity.confidence if entity.confidence is not None else 0.5
            claims.append(_claim(observation, kind, semantic_id, "present_in", observation.scene_id, confidence))
            if semantic_id not in prior_labels:
                claims.append(_claim(observation, "timeline_change", semantic_id, "appears_in", observation.scene_id, confidence))
        for action in observation.actions:
            claims.append(_claim(observation, "event", _stable_id("event", action), "occurs_in", observation.scene_id, 0.5, action))
        for interaction in observation.interactions:
            claims.append(_claim(observation, "relationship", _stable_id("interaction", interaction), "observed_in", observation.scene_id, 0.5, interaction))
        state = _scene_state(perception)
        if state:
            claims.append(_claim(observation, "scene_state", _stable_id("scene", observation.scene_id), "has_state", observation.scene_id, _scene_confidence(perception), state))
        return _unique(claims)


def _claim(observation: FrameObservation, kind, subject_id, predicate, object_id, confidence, value: str = "") -> SemanticClaim:
    token = f"{kind}:{observation.scene_id}:{subject_id}:{predicate}:{object_id}:{value}"
    return SemanticClaim(
        id=_stable_id("claim", token), kind=kind, scene_id=observation.scene_id,
        timestamp_seconds=observation.timestamp_seconds, subject_id=subject_id,
        predicate=predicate, object_id=object_id, value=value, confidence=confidence,
        observation_ids=[observation.id],
    )


def _scene_state(perception: UnifiedSceneRepresentation) -> str:
    labels = list(dict.fromkeys(entity.label for entity in perception.entities if entity.category in {"person", "animal", "object"}))
    if not labels and not perception.actions:
        return "No semantic scene state could be established."
    fragments = [f"Visible: {', '.join(labels)}." if labels else ""]
    if perception.actions:
        fragments.append(f"Actions: {', '.join(perception.actions)}.")
    return " ".join(fragment for fragment in fragments if fragment)


def _scene_confidence(perception: UnifiedSceneRepresentation) -> float:
    values = [entity.confidence for entity in perception.entities if entity.confidence is not None]
    return sum(values) / len(values) if values else 0.5


def _stable_id(kind: str, value: str) -> str:
    return f"{kind}-{sha256(value.lower().encode('utf-8')).hexdigest()[:16]}"


def _unique(claims: list[SemanticClaim]) -> list[SemanticClaim]:
    return list({claim.id: claim for claim in claims}.values())
