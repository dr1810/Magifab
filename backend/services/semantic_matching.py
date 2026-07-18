"""Contextual semantic matching over authoritative movie knowledge.

Perception contributes evidence about the current frame.  It is deliberately
not the authority for a character's identity: catalog scene membership,
timeline placement and previously established semantic claims provide that
authority for supported movies.
"""
from config import Settings
from models.semantic_matcher import SemanticMatcher
from schemas.fusion import UnifiedEntity, UnifiedSceneRepresentation
from schemas.knowledge import MovieSceneKnowledge, SemanticMovieKnowledge
from schemas.matching import CharacterMatch, MatchedFact, SemanticMatchResult


class SemanticMatchingService(SemanticMatcher):
    """Match perception evidence against a movie's scene-aware semantic graph."""

    def __init__(self, settings: Settings):
        self._threshold = settings.semantic_match_confidence_threshold

    def match(
        self,
        scene: UnifiedSceneRepresentation,
        knowledge: SemanticMovieKnowledge,
        *,
        scene_id: str | None = None,
        timestamp_seconds: float | None = None,
    ) -> SemanticMatchResult:
        """Return catalog-backed facts, optionally scoped to a prepared scene.

        ``scene_id`` and ``timestamp_seconds`` are internal preparation context,
        not a public API requirement.  The /match API remains compatible and
        simply performs evidence-only matching when they are omitted.
        """
        catalog_scene = _catalog_scene(knowledge, scene_id, timestamp_seconds)
        nearby_scenes = _nearby_scenes(knowledge, catalog_scene)
        characters = self._match_characters(scene, knowledge, catalog_scene, nearby_scenes, timestamp_seconds)
        locations = self._match_locations(scene, knowledge, catalog_scene, timestamp_seconds)
        objects = self._match_objects(scene, knowledge, catalog_scene)
        relationships = self._match_relationships(characters, knowledge, catalog_scene)
        events = self._match_events(scene, knowledge, catalog_scene)
        timeline_positions = self._match_timeline(events, knowledge, timestamp_seconds)
        return SemanticMatchResult(
            character_found=bool(characters), characters=characters, locations=locations, objects=objects,
            relationships=relationships, events=events, timeline_positions=timeline_positions,
        )

    def _match_characters(self, scene, knowledge, catalog_scene, nearby_scenes, timestamp_seconds):
        exact_matches: list[CharacterMatch] = []
        matched_ids: set[str] = set()
        for entity in scene.entities:
            verified_ids = set(entity.visual_attributes.get("verified_character_id", []))
            candidates = [character for character in knowledge.characters if character.id in verified_ids] or [
                character for character in knowledge.characters
                if _matches(entity.label, [*character.perception_labels, *character.aliases, character.name])
            ]
            if len(candidates) != 1:
                continue
            character = candidates[0]
            confidence = entity.confidence if entity.confidence is not None else 0.5
            # A known label is useful evidence even when Florence supplies no
            # box confidence; do not discard it solely for that reason.
            if confidence < self._threshold and "scene_understanding" not in entity.sources and not verified_ids:
                continue
            exact_matches.append(CharacterMatch(
                id=character.id, label=character.name, confidence=max(confidence, 0.8),
                evidence=[
                    f"entity:{entity.label}",
                    "face_embedding_identity" if character.id in verified_ids else "catalog_alias_evidence",
                ], entity=entity,
            ))
            matched_ids.add(character.id)

        if catalog_scene is None:
            return _unique_facts(exact_matches)

        # The catalog is primary for a supported movie.  A curated scene says
        # who participates; current-frame labels only corroborate that fact.
        # This avoids losing Victoria merely because Florence calls her a
        # "young boy" or YOLO emits the generic "person" label.
        character_by_id = {character.id: character for character in knowledge.characters}
        history_ids = _previous_character_ids(knowledge, timestamp_seconds)
        nearby_ids = {item for nearby in nearby_scenes for item in nearby.character_ids}
        generic_evidence = _generic_person_evidence(scene)
        for character_id in catalog_scene.character_ids:
            if character_id in matched_ids or character_id not in character_by_id:
                continue
            character = character_by_id[character_id]
            evidence = [f"catalog_scene:{catalog_scene.scene_id}", "known_scene_participant"]
            confidence = 0.82
            if character_id in history_ids:
                confidence = 0.9
                evidence.append("previous_semantic_memory")
            if character_id in nearby_ids:
                confidence = max(confidence, 0.86)
                evidence.append("neighboring_scene_continuity")
            if generic_evidence is not None:
                evidence.append(f"perception_evidence:{generic_evidence.label}")
            exact_matches.append(CharacterMatch(
                id=character.id,
                label=character.name,
                confidence=confidence,
                evidence=evidence,
                # This is evidence of a person/animal in the frame, not a
                # textual identity assertion. The graph builder recognizes the
                # catalog evidence and emits an independent participant claim.
                entity=generic_evidence or UnifiedEntity(
                    label=f"catalog participant: {character.name}", category="person",
                    confidence=None, sources=["movie_knowledge"],
                ),
            ))
        return _unique_facts(exact_matches)

    def _match_locations(self, scene, knowledge, catalog_scene, timestamp_seconds):
        matches = []
        for location in knowledge.locations:
            if scene.environment and _matches(scene.environment, [*location.aliases, location.name]):
                matches.append(MatchedFact(id=location.id, label=location.name, confidence=0.85,
                                           evidence=[f"environment:{scene.environment}", "catalog_location_alias"]))
        # A timeline/scene alone is supporting context, never an invented
        # location. Catalog location aliases still make the final association.
        return _unique_facts(matches)

    def _match_objects(self, scene, knowledge, catalog_scene):
        # An omitted/empty scene list means the catalog has no object
        # annotation for that scene, not that every known object is absent.
        allowed_ids = set(catalog_scene.object_ids) if catalog_scene and catalog_scene.object_ids else None
        matches = []
        for entity in scene.entities:
            candidates = [
                obj for obj in knowledge.objects
                if (allowed_ids is None or obj.id in allowed_ids)
                and _matches(entity.label, [*obj.perception_labels, *obj.aliases, obj.name])
            ]
            if len(candidates) != 1:
                continue
            obj = candidates[0]
            confidence = entity.confidence if entity.confidence is not None else 0.5
            if confidence >= self._threshold or "scene_understanding" in entity.sources:
                matches.append(MatchedFact(id=obj.id, label=obj.name, confidence=max(confidence, 0.8),
                                           evidence=[f"entity:{entity.label}", "catalog_object_alias"]))
        return _unique_facts(matches)

    def _match_relationships(self, characters, knowledge, catalog_scene):
        character_ids = {character.id for character in characters}
        # Use explicit scene relationship annotations when available; otherwise
        # the movie relationship graph and active participants provide the
        # continuity evidence.
        allowed_ids = set(catalog_scene.relationship_ids) if catalog_scene and catalog_scene.relationship_ids else None
        matches = []
        for relationship in knowledge.relationships:
            if allowed_ids is not None and relationship.id not in allowed_ids:
                continue
            if relationship.from_character_id not in character_ids or relationship.to_character_id not in character_ids:
                continue
            confidence = min(
                next(character.confidence for character in characters if character.id == relationship.from_character_id),
                next(character.confidence for character in characters if character.id == relationship.to_character_id),
            )
            matches.append(MatchedFact(id=relationship.id, label=relationship.description, confidence=confidence,
                                       evidence=["catalog_relationship_graph", "known_participants_active"]))
        return _unique_facts(matches)

    def _match_events(self, scene, knowledge, catalog_scene):
        observed_terms = {_normalize(value) for value in [scene.environment, *scene.actions, *(entity.label for entity in scene.entities)] if value}
        allowed_ids = set(catalog_scene.event_ids) if catalog_scene else set()
        matches = []
        for event in knowledge.events:
            required = {_normalize(term) for term in event.evidence_terms if term.strip()}
            if event.id in allowed_ids:
                matches.append(MatchedFact(id=event.id, label=event.description, confidence=0.86,
                                           evidence=[f"catalog_scene:{catalog_scene.scene_id}", "catalog_scene_event"]))
            elif required and required.issubset(observed_terms):
                matches.append(MatchedFact(id=event.id, label=event.description, confidence=0.8,
                                           evidence=[f"terms:{','.join(sorted(required))}", "perception_event_evidence"]))
        return _unique_facts(matches)

    def _match_timeline(self, events, knowledge, timestamp_seconds):
        positions = []
        if timestamp_seconds is not None:
            positions.extend(MatchedFact(id=item.id, label=item.description, confidence=0.9,
                                        evidence=[f"timestamp:{timestamp_seconds:.3f}", "catalog_timeline_range"])
                             for item in knowledge.timeline_positions if item.start_seconds <= timestamp_seconds <= item.end_seconds)
        by_id = {item.id: item for item in knowledge.timeline_positions}
        for event in events:
            source = next((item for item in knowledge.events if item.id == event.id), None)
            position = by_id.get(source.timeline_position_id or "") if source else None
            if position:
                positions.append(MatchedFact(id=position.id, label=position.description, confidence=event.confidence,
                                             evidence=[f"event:{event.id}", "catalog_event_timeline_link"]))
        return _unique_facts(positions)


def _catalog_scene(knowledge, scene_id, timestamp_seconds) -> MovieSceneKnowledge | None:
    if scene_id:
        item = next((scene for scene in knowledge.movie_scenes if scene.scene_id == scene_id), None)
        if item is not None:
            return item
    if timestamp_seconds is not None:
        return next((scene for scene in knowledge.movie_scenes if scene.start_seconds <= timestamp_seconds <= scene.end_seconds), None)
    return None


def _nearby_scenes(knowledge, current):
    if current is None:
        return []
    scenes = sorted(knowledge.movie_scenes, key=lambda item: item.start_seconds)
    index = next((index for index, item in enumerate(scenes) if item.scene_id == current.scene_id), -1)
    return [item for item in scenes[max(0, index - 1):index + 2] if item.scene_id != current.scene_id]


def _previous_character_ids(knowledge, timestamp_seconds):
    if timestamp_seconds is None:
        return set()
    return {claim.subject_id for claim in knowledge.semantic_claims
            if claim.kind == "character_present" and claim.timestamp_seconds < timestamp_seconds}


def _generic_person_evidence(scene):
    return next((entity for entity in scene.entities if entity.category in {"person", "animal"}), None)


def _matches(value: str, aliases: list[str]) -> bool:
    normalized = _normalize(value)
    return bool(normalized) and normalized in {_normalize(alias) for alias in aliases}


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def _unique_facts(facts: list[MatchedFact]) -> list:
    seen: set[str] = set()
    result = []
    for fact in facts:
        if fact.id not in seen:
            seen.add(fact.id)
            result.append(fact)
    return result
