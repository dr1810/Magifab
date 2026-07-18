"""Retrieves a bounded graph-only context for the accessibility reasoner."""
from schemas.knowledge import SemanticMovieKnowledge
from schemas.profiles import AccessibilityProfile
from schemas.reasoning_context import ContextRelationship, ReasoningContext, ReasoningEntity


class ReasoningContextBuilder:
    """Selects semantic claims; it never returns raw observations or perception fields."""

    def build(self, *, knowledge: SemanticMovieKnowledge, scene_id: str, timestamp_seconds: float, accessibility_profile: AccessibilityProfile) -> ReasoningContext:
        scene_claims = [claim for claim in knowledge.semantic_claims if claim.scene_id == scene_id]
        active_character_claims = [claim for claim in scene_claims if claim.kind == "character_present"]
        active_object_claims = [claim for claim in scene_claims if claim.kind == "object_present"]
        character_by_id = {character.id: character for character in knowledge.characters}
        object_by_id = {item.id: item for item in knowledge.objects}
        active_ids = {claim.subject_id for claim in active_character_claims}
        relationships = [
            relationship for relationship in knowledge.relationships
            if relationship.from_character_id in active_ids and relationship.to_character_id in active_ids
        ]
        relationship_claims = [claim for claim in scene_claims if claim.kind == "relationship"]
        timeline_claims = [claim for claim in scene_claims if claim.kind == "timeline_change"]
        timeline = next((item for item in knowledge.timeline_positions if item.start_seconds <= timestamp_seconds <= item.end_seconds), None)
        return ReasoningContext(
            movie_id=knowledge.movie_id,
            scene_id=scene_id,
            timestamp_seconds=timestamp_seconds,
            accessibility_profile=accessibility_profile,
            semantic_scene=scene_claims,
            active_characters=_entities(active_character_claims, character_by_id),
            active_objects=_entities(active_object_claims, object_by_id),
            timeline=timeline,
            timeline_claim_ids=[claim.id for claim in timeline_claims],
            relationships=[
                ContextRelationship(
                    id=relationship.id,
                    description=relationship.description,
                    confidence=min(character_by_id[relationship.from_character_id].confidence, character_by_id[relationship.to_character_id].confidence),
                    claim_ids=[claim.id for claim in relationship_claims],
                )
                for relationship in relationships
                if relationship.from_character_id in character_by_id and relationship.to_character_id in character_by_id
            ],
            previous_events=[
                claim for claim in knowledge.semantic_claims
                if claim.kind == "event" and claim.timestamp_seconds < timestamp_seconds
            ][-6:],
            previous_character_presence=[
                claim for claim in knowledge.semantic_claims
                if claim.kind == "character_present" and claim.timestamp_seconds < timestamp_seconds
            ][-12:],
            emotion_claims=[claim for claim in scene_claims if claim.kind == "emotion"],
            vocabulary_claims=[claim for claim in scene_claims if claim.kind == "callback" and claim.predicate == "defines"],
            conversation_claims=[claim for claim in scene_claims if claim.kind == "callback" and claim.predicate == "dialogue"],
        )


def _entities(claims, entities_by_id) -> list[ReasoningEntity]:
    """Only registered semantic entities receive display names in a user context."""
    result: list[ReasoningEntity] = []
    seen: set[str] = set()
    for claim in claims:
        entity = entities_by_id.get(claim.subject_id)
        if entity is None or entity.id in seen:
            continue
        seen.add(entity.id)
        result.append(ReasoningEntity(id=entity.id, name=entity.name, confidence=entity.confidence, claim_ids=[claim.id]))
    return result
