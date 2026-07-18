"""Conservative semantic matching; this service deliberately contains no GPT or perception code."""
from config import Settings
from models.semantic_matcher import SemanticMatcher
from schemas.fusion import UnifiedSceneRepresentation
from schemas.knowledge import SemanticMovieKnowledge
from schemas.matching import CharacterMatch, MatchedFact, SemanticMatchResult


class SemanticMatchingService(SemanticMatcher):
    """Matches exact, unambiguous knowledge aliases above a configured confidence threshold."""

    def __init__(self, settings: Settings):
        self._threshold = settings.semantic_match_confidence_threshold

    def match(self, scene: UnifiedSceneRepresentation, knowledge: SemanticMovieKnowledge) -> SemanticMatchResult:
        characters = self._match_characters(scene, knowledge)
        locations = self._match_locations(scene, knowledge)
        objects = self._match_objects(scene, knowledge)
        relationships = self._match_relationships(characters, knowledge)
        events = self._match_events(scene, knowledge)
        timeline_positions = self._match_timeline(events, knowledge)
        return SemanticMatchResult(
            character_found=bool(characters), characters=characters, locations=locations, objects=objects,
            relationships=relationships, events=events, timeline_positions=timeline_positions,
        )

    def _match_characters(self, scene: UnifiedSceneRepresentation, knowledge: SemanticMovieKnowledge) -> list[CharacterMatch]:
        matches: list[CharacterMatch] = []
        for entity in scene.entities:
            confidence = entity.confidence or 0.0
            candidates = [character for character in knowledge.characters if _matches(entity.label, character.perception_labels)]
            if len(candidates) != 1 or confidence < self._threshold:
                continue
            character = candidates[0]
            matches.append(CharacterMatch(
                id=character.id, label=character.name, confidence=confidence,
                evidence=[f"entity:{entity.label}", "exact_perception_label"], entity=entity,
            ))
        return _unique_facts(matches)

    def _match_locations(self, scene: UnifiedSceneRepresentation, knowledge: SemanticMovieKnowledge) -> list[MatchedFact]:
        if not scene.environment:
            return []
        candidates = [location for location in knowledge.locations if _matches(scene.environment, location.aliases)]
        if len(candidates) != 1:
            return []
        location = candidates[0]
        return [MatchedFact(id=location.id, label=location.name, confidence=0.85, evidence=[f"environment:{scene.environment}", "exact_location_alias"])]

    def _match_objects(self, scene: UnifiedSceneRepresentation, knowledge: SemanticMovieKnowledge) -> list[MatchedFact]:
        matches: list[MatchedFact] = []
        for entity in scene.entities:
            confidence = entity.confidence or 0.0
            candidates = [obj for obj in knowledge.objects if _matches(entity.label, obj.perception_labels)]
            if len(candidates) != 1 or confidence < self._threshold:
                continue
            obj = candidates[0]
            matches.append(MatchedFact(id=obj.id, label=obj.name, confidence=confidence, evidence=[f"entity:{entity.label}", "exact_perception_label"]))
        return _unique_facts(matches)

    def _match_relationships(self, characters: list[CharacterMatch], knowledge: SemanticMovieKnowledge) -> list[MatchedFact]:
        character_ids = {character.id for character in characters}
        matches: list[MatchedFact] = []
        for relationship in knowledge.relationships:
            if relationship.from_character_id not in character_ids or relationship.to_character_id not in character_ids:
                continue
            confidence = min(
                next(character.confidence for character in characters if character.id == relationship.from_character_id),
                next(character.confidence for character in characters if character.id == relationship.to_character_id),
            )
            matches.append(MatchedFact(id=relationship.id, label=relationship.description, confidence=confidence, evidence=["both_relationship_characters_verified"]))
        return matches

    def _match_events(self, scene: UnifiedSceneRepresentation, knowledge: SemanticMovieKnowledge) -> list[MatchedFact]:
        observed_terms = {_normalize(value) for value in [scene.environment, *scene.actions, *(entity.label for entity in scene.entities)] if value}
        matches: list[MatchedFact] = []
        for event in knowledge.events:
            required = {_normalize(term) for term in event.evidence_terms if term.strip()}
            if not required or not required.issubset(observed_terms):
                continue
            matches.append(MatchedFact(id=event.id, label=event.description, confidence=1.0, evidence=[f"terms:{','.join(sorted(required))}", "all_event_terms_observed"]))
        return matches

    def _match_timeline(self, events: list[MatchedFact], knowledge: SemanticMovieKnowledge) -> list[MatchedFact]:
        matched_event_ids = {event.id: event.confidence for event in events}
        timeline_by_id = {position.id: position for position in knowledge.timeline_positions}
        matches: list[MatchedFact] = []
        for event in knowledge.events:
            confidence = matched_event_ids.get(event.id)
            position = timeline_by_id.get(event.timeline_position_id or "")
            if confidence is None or position is None:
                continue
            matches.append(MatchedFact(id=position.id, label=position.description, confidence=confidence, evidence=[f"event:{event.id}", "verified_event_timeline_link"]))
        return _unique_facts(matches)


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
