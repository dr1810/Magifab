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
        self._presence_threshold = settings.semantic_presence_confidence_threshold

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
        """Separate scene membership from evidence-weighted visual presence."""
        participant_ids = set(catalog_scene.character_ids) if catalog_scene else set()
        direct_evidence = _direct_character_evidence(scene, knowledge)
        # For a catalog scene, its cast list is the authoritative scope. A
        # detector alias outside that scope must not surface a global movie
        # character in this scene's cards. Unsupported scenes retain the
        # evidence-only fallback for backward compatibility.
        candidate_ids = participant_ids if catalog_scene is not None else set(direct_evidence)
        previous = _previous_presence(knowledge, timestamp_seconds)
        nearby_ids = {item for nearby in nearby_scenes for item in nearby.character_ids}
        matches: list[CharacterMatch] = []

        # Preserve catalog declaration order so prepared cards are stable for
        # the same movie/scene/timestamp across process restarts.
        for character in (item for item in knowledge.characters if item.id in candidate_ids):
            character_id = character.id
            direct = direct_evidence.get(character_id)
            scores = {
                "scene_catalogue": 1.0 if character_id in participant_ids else 0.0,
                "timeline": 0.95 if catalog_scene is not None else 0.0,
                "visual_detection": direct["visual"] if direct else 0.0,
                "grounding": direct["grounding"] if direct else 0.0,
                # Captions describe a frame but never identify its cast.
                "caption": 0.0,
                "temporal_continuity": previous.get(character_id, 0.0),
            }
            confidence = _presence_confidence(scores)
            state = _presence_state(confidence, direct, self._presence_threshold)
            evidence = [
                *( [f"catalog_scene:{catalog_scene.scene_id}", "known_scene_participant"] if character_id in participant_ids else [] ),
                *(direct["evidence"] if direct else []),
                *( ["neighboring_scene_continuity"] if character_id in nearby_ids else [] ),
                *( ["previous_semantic_memory"] if scores["temporal_continuity"] else [] ),
                *(f"presence_{name}:{score:.2f}" for name, score in scores.items()),
                f"presence_state:{state}",
            ]
            entity = direct["entity"] if direct else UnifiedEntity(
                label=f"catalog participant: {character.name}", category="person",
                confidence=None, sources=["movie_knowledge"],
            )
            matches.append(CharacterMatch(
                id=character.id, label=character.name, confidence=confidence,
                evidence=evidence, entity=entity,
            ))
        return _unique_facts(matches)

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
            # Florence's text-only object list is descriptive enrichment, not
            # visibility proof.  Only a boxed detector/grounding result can
            # promote a catalog object into the semantic graph.
            if confidence >= self._threshold and any(source in {"object_detection", "object_grounding"} for source in entity.sources):
                matches.append(MatchedFact(id=obj.id, label=obj.name, confidence=max(confidence, 0.8),
                                           evidence=[f"entity:{entity.label}", "catalog_object_alias"]))
        return _unique_facts(matches)

    def _match_relationships(self, characters, knowledge, catalog_scene):
        character_ids = {
            character.id for character in characters
            if _presence_is_active(character.evidence)
        }
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


def _previous_presence(knowledge, timestamp_seconds):
    if timestamp_seconds is None:
        return {}
    # Only prior claims that were themselves sufficiently supported can carry
    # identity forward. A scene-membership claim can never snowball into proof.
    previous: dict[str, float] = {}
    for claim in knowledge.semantic_claims:
        if claim.kind != "character_present" or claim.timestamp_seconds >= timestamp_seconds:
            continue
        age = timestamp_seconds - claim.timestamp_seconds
        if age > 15:
            continue
        previous[claim.subject_id] = max(previous.get(claim.subject_id, 0.0), claim.confidence * (1 - age / 20))
    return previous


def _direct_character_evidence(scene, knowledge):
    """Collect identity evidence by provider; generic people identify nobody."""
    result: dict[str, dict] = {}
    for entity in scene.entities:
        verified_ids = set(entity.visual_attributes.get("verified_character_id", []))
        aliases = [
            character for character in knowledge.characters
            if _matches(entity.label, [*character.perception_labels, *character.aliases, character.name])
        ]
        candidates = [character for character in knowledge.characters if character.id in verified_ids] or aliases
        if len(candidates) != 1:
            continue
        character = candidates[0]
        score = entity.confidence if entity.confidence is not None else 0.5
        item = result.setdefault(character.id, {"visual": 0.0, "grounding": 0.0, "caption": 0.0, "face_verified": False, "evidence": [], "entity": entity})
        item["entity"] = entity if score >= (item["entity"].confidence or 0.0) else item["entity"]
        if character.id in verified_ids:
            item["visual"] = max(item["visual"], max(score, 0.95))
            item["face_verified"] = True
            item["evidence"].append("face_embedding_identity")
        if "object_detection" in entity.sources:
            item["visual"] = max(item["visual"], score)
            item["evidence"].append(f"yolo_identity:{entity.label}")
        if "object_grounding" in entity.sources:
            item["grounding"] = max(item["grounding"], score)
            item["evidence"].append(f"grounding_identity:{entity.label}")
    return result


def _presence_confidence(scores: dict[str, float]) -> float:
    """Weighted, bounded evidence score; scene membership alone stays weak."""
    weights = {
        "scene_catalogue": 0.25,
        "timeline": 0.20,
        "visual_detection": 0.30,
        "grounding": 0.15,
        "caption": 0.05,
        "temporal_continuity": 0.05,
    }
    return round(sum(weights[name] * scores[name] for name in weights), 3)


def _presence_state(confidence: float, direct, threshold: float) -> str:
    if direct and direct["face_verified"]:
        return "visually_confirmed"
    # A successful DINO match was queried from the current scene's catalog;
    # it is direct visibility confirmation, not a caption guess.
    if direct and direct["grounding"] > 0:
        return "visually_confirmed"
    return "likely_present" if confidence >= threshold else "scene_member"


def _presence_is_active(evidence: list[str]) -> bool:
    return any(value in {"presence_state:likely_present", "presence_state:visually_confirmed"} for value in evidence)


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
