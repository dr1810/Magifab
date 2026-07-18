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
        # Only direct perception aliases may bind a particular frame entity to
        # an identity. Contextual catalog matches establish participant
        # presence separately below; they must not pretend that a generic
        # Florence label (for example, "young boy") is a name.
        verified = {
            match.entity.label.lower(): match
            for match in matches.characters
            if {"catalog_alias_evidence", "face_embedding_identity"}.intersection(match.evidence)
        }
        claims: list[SemanticClaim] = []
        prior_labels = {
            claim.subject_id for claim in existing.semantic_claims
            if claim.timestamp_seconds < observation.timestamp_seconds and claim.kind in {"character_present", "object_present"}
        }
        for entity in perception.entities:
            if entity.category not in {"person", "animal", "object"}:
                continue
            character_match = verified.get(entity.label.lower())
            object_match = _object_match(entity.label, matches, existing)
            semantic_id = (character_match.id if character_match else object_match.id if object_match else _stable_id(entity.category, entity.label))
            kind = "character_present" if entity.category in {"person", "animal"} else "object_present"
            confidence = entity.confidence if entity.confidence is not None else 0.5
            knowledge_ids = [character_match.id] if character_match else [object_match.id] if object_match else []
            claims.append(_claim(
                observation, kind, semantic_id, "present_in", observation.scene_id, confidence,
                knowledge_ids=knowledge_ids,
            ))
            if semantic_id not in prior_labels:
                claims.append(_claim(observation, "timeline_change", semantic_id, "appears_in", observation.scene_id, confidence))
        emitted_character_ids = {claim.subject_id for claim in claims if claim.kind == "character_present"}
        for character in matches.characters:
            if character.id in emitted_character_ids or "known_scene_participant" not in character.evidence:
                continue
            claims.append(_claim(
                observation, "character_present", character.id, "present_in", observation.scene_id,
                character.confidence, evidence_origin="movie_knowledge_supported", knowledge_ids=[character.id],
            ))
            if character.id not in prior_labels:
                claims.append(_claim(
                    observation, "timeline_change", character.id, "appears_in", observation.scene_id,
                    character.confidence, evidence_origin="movie_knowledge_supported", knowledge_ids=[character.id],
                ))
        for action in observation.actions:
            claims.append(_claim(observation, "event", _stable_id("event", action), "occurs_in", observation.scene_id, 0.5, action))
        for interaction in observation.interactions:
            claims.append(_claim(observation, "relationship", _stable_id("interaction", interaction), "observed_in", observation.scene_id, 0.5, interaction))
        # A matched catalog event is a supported semantic fact. It remains
        # traceable to the exact frame observation that satisfied its evidence
        # terms, rather than replacing anything Florence or YOLO observed.
        for event in matches.events:
            claims.append(_claim(
                observation, "event", event.id, "occurs_in", observation.scene_id, event.confidence,
                event.label, evidence_origin="movie_knowledge_supported", knowledge_ids=[event.id],
            ))
        for relationship in matches.relationships:
            claims.append(_claim(
                observation, "relationship", relationship.id, "active_in", observation.scene_id,
                relationship.confidence, relationship.label,
                evidence_origin="movie_knowledge_supported", knowledge_ids=[relationship.id],
            ))
        state = _scene_state(perception, matches)
        if state:
            claims.append(_claim(observation, "scene_state", _stable_id("scene", observation.scene_id), "has_state", observation.scene_id, _scene_confidence(perception), state))
        return _unique(claims)


def _claim(
    observation: FrameObservation,
    kind,
    subject_id,
    predicate,
    object_id,
    confidence,
    value: str = "",
    *,
    evidence_origin: str = "perception_verified",
    knowledge_ids: list[str] | None = None,
) -> SemanticClaim:
    token = f"{kind}:{observation.scene_id}:{subject_id}:{predicate}:{object_id}:{value}"
    return SemanticClaim(
        id=_stable_id("claim", token), kind=kind, scene_id=observation.scene_id,
        timestamp_seconds=observation.timestamp_seconds, subject_id=subject_id,
        predicate=predicate, object_id=object_id, value=value, confidence=confidence,
        observation_ids=[observation.id], evidence_origin=evidence_origin,
        knowledge_ids=knowledge_ids or [],
    )


def _scene_state(perception: UnifiedSceneRepresentation, matches: SemanticMatchResult) -> str:
    matched_names = [*([item.label for item in matches.characters]), *([item.label for item in matches.objects])]
    matched_labels = {
        item.entity.label.lower() for item in matches.characters
    }
    labels = list(dict.fromkeys([
        *matched_names,
        *(entity.label for entity in perception.entities
          if entity.category in {"person", "animal", "object"} and entity.label.lower() not in matched_labels),
    ]))
    if not labels and not perception.actions:
        return "No semantic scene state could be established."
    fragments = [f"Visible: {', '.join(labels)}." if labels else ""]
    if perception.actions:
        fragments.append(f"Actions: {', '.join(perception.actions)}.")
    return " ".join(fragment for fragment in fragments if fragment)


def _object_match(label: str, matches: SemanticMatchResult, knowledge: SemanticMovieKnowledge):
    """Resolve an object match back to its frame label without trusting a name alone."""
    normalized = label.strip().lower()
    for match in matches.objects:
        item = next((candidate for candidate in knowledge.objects if candidate.id == match.id), None)
        aliases = [*item.perception_labels, *item.aliases, item.name] if item else [match.label]
        if normalized in {value.strip().lower() for value in aliases}:
            return match
    return None


def _scene_confidence(perception: UnifiedSceneRepresentation) -> float:
    values = [entity.confidence for entity in perception.entities if entity.confidence is not None]
    return sum(values) / len(values) if values else 0.5


def _stable_id(kind: str, value: str) -> str:
    return f"{kind}-{sha256(value.lower().encode('utf-8')).hexdigest()[:16]}"


def _unique(claims: list[SemanticClaim]) -> list[SemanticClaim]:
    return list({claim.id: claim for claim in claims}.values())
