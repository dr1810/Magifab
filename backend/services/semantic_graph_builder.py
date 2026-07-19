"""Converts raw observations into provenance-backed semantic movie claims."""
from hashlib import sha256

from schemas.fusion import UnifiedSceneRepresentation
from schemas.knowledge import SemanticMovieKnowledge
from schemas.matching import SemanticMatchResult
from schemas.observation import FrameObservation
from schemas.semantic_graph import SemanticClaim


class SemanticGraphBuilder:
    """Turns catalog facts and verified perception into provenance-backed claims."""

    def build(
        self,
        *,
        observation: FrameObservation,
        perception: UnifiedSceneRepresentation,
        matches: SemanticMatchResult,
        existing: SemanticMovieKnowledge,
    ) -> list[SemanticClaim]:
        # Only direct, catalog-query evidence may bind a frame entity to an
        # identity.  A Florence caption (for example, "young boy") is never a
        # character identity and a generic YOLO "person" is never a character.
        verified = {
            match.entity.label.lower(): match
            for match in matches.characters
            if _direct_identity_evidence(match.evidence) and _presence_is_active(match.evidence)
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
            # Do not promote unrecognized detector labels into graph facts.
            # This is what formerly produced object_present(person), then
            # generic caption-derived explanations and prompts.
            if character_match is None and object_match is None:
                continue
            semantic_id = character_match.id if character_match else object_match.id
            kind = "character_present" if character_match else "object_present"
            catalog_character = next((item for item in existing.characters if character_match and item.id == character_match.id), None)
            confidence = (
                catalog_character.confidence if catalog_character else character_match.confidence
            ) if character_match else (entity.confidence if entity.confidence is not None else 0.5)
            knowledge_ids = [character_match.id] if character_match else [object_match.id] if object_match else []
            claims.append(_claim(
                observation, kind, semantic_id, "present_in", observation.scene_id, confidence,
                knowledge_ids=knowledge_ids,
            ))
            if semantic_id not in prior_labels:
                claims.append(_claim(observation, "timeline_change", semantic_id, "appears_in", observation.scene_id, confidence))
        emitted_character_ids = {claim.subject_id for claim in claims if claim.kind == "character_present"}
        for character in matches.characters:
            if (
                character.id in emitted_character_ids
                or "known_scene_participant" not in character.evidence
            ):
                continue
            # Scene membership is a curated movie fact.  It survives a missing
            # DINO/YOLO result so a model failure cannot erase the cast from a
            # prepared scene.  Generic captions still cannot reach this path:
            # SemanticMatchingService creates these matches from the catalog.
            catalog_character = next((item for item in existing.characters if item.id == character.id), None)
            confidence = catalog_character.confidence if catalog_character else character.confidence
            claims.append(_claim(
                observation, "character_present", character.id, "present_in", observation.scene_id,
                confidence, evidence_origin="movie_knowledge_supported", knowledge_ids=[character.id],
            ))
            if character.id not in prior_labels:
                claims.append(_claim(
                    observation, "timeline_change", character.id, "appears_in", observation.scene_id,
                    confidence, evidence_origin="movie_knowledge_supported", knowledge_ids=[character.id],
                ))
        # Florence actions and interactions stay attached to the raw
        # observation. They can corroborate a catalog event during matching,
        # but may never become standalone events/relationships.
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
        # The catalog timeline is a stable scene fact, not a side effect of a
        # character appearing.  Recording it gives presentation a traceable
        # timeline summary even for a visually quiet frame.
        for timeline in matches.timeline_positions:
            claims.append(_claim(
                observation, "timeline_change", timeline.id, "active_at", observation.scene_id,
                timeline.confidence, timeline.label,
                evidence_origin="movie_knowledge_supported", knowledge_ids=[timeline.id],
            ))
        # Curated emotional context is movie knowledge, not a caption-derived
        # guess. It can therefore create an accessibility prompt without a
        # fresh visual match on every frame.
        for emotion in existing.emotions:
            if emotion.scene_id not in {None, observation.scene_id}:
                continue
            claims.append(_claim(
                observation, "emotion", emotion.character_id or emotion.id, "feels", observation.scene_id,
                emotion.confidence, emotion.emotion,
                evidence_origin="movie_knowledge_supported", knowledge_ids=[emotion.id],
            ))
        state = _scene_state(perception, matches, existing, observation.scene_id)
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


def _scene_state(perception: UnifiedSceneRepresentation, matches: SemanticMatchResult, existing: SemanticMovieKnowledge | None = None, scene_id: str | None = None) -> str:
    """Describe story context and confirmed catalog entities, never scenery."""
    catalog_scene = next((item for item in (existing.movie_scenes if existing else []) if item.scene_id == scene_id), None)
    confirmed_characters = [item.label for item in matches.characters if _direct_identity_evidence(item.evidence) and _presence_is_active(item.evidence)]
    confirmed_objects = [item.label for item in matches.objects]
    story = catalog_scene.description if catalog_scene else ""
    visible = list(dict.fromkeys([*confirmed_characters, *confirmed_objects]))
    if story and confirmed_characters:
        return f"{story} Visible now: {', '.join(visible)}."
    if confirmed_characters:
        return f"Visible now: {', '.join(visible)}."
    if story:
        return story
    return "No story-relevant entity has been confirmed in this frame."


def _object_match(label: str, matches: SemanticMatchResult, knowledge: SemanticMovieKnowledge):
    """Resolve an object match back to its frame label without trusting a name alone."""
    normalized = label.strip().lower()
    for match in matches.objects:
        item = next((candidate for candidate in knowledge.objects if candidate.id == match.id), None)
        aliases = [*item.perception_labels, *item.aliases, item.name] if item else [match.label]
        if normalized in {value.strip().lower() for value in aliases}:
            return match
    return None


def _direct_identity_evidence(evidence: list[str]) -> bool:
    return any(value == "face_embedding_identity" or value.startswith(("yolo_identity:", "grounding_identity:")) for value in evidence)


def _presence_is_active(evidence: list[str]) -> bool:
    return any(value in {"presence_state:likely_present", "presence_state:visually_confirmed"} for value in evidence)


def _scene_confidence(perception: UnifiedSceneRepresentation) -> float:
    values = [entity.confidence for entity in perception.entities if entity.confidence is not None]
    return sum(values) / len(values) if values else 0.5


def _stable_id(kind: str, value: str) -> str:
    return f"{kind}-{sha256(value.lower().encode('utf-8')).hexdigest()[:16]}"


def _unique(claims: list[SemanticClaim]) -> list[SemanticClaim]:
    return list({claim.id: claim for claim in claims}.values())
