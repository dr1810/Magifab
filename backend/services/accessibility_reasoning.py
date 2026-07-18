"""Deterministic accessibility content generation from verified Semantic Movie Knowledge."""
import logging
from time import perf_counter
from models.accessibility_reasoner import AccessibilityReasoner
from schemas.accessibility_reasoning import (
    AccessibilityDrawerContent,
    AccessibilityReasoningRequest,
    AccessibilityReasoningResult,
    CharacterCard,
    ConfusionPrediction,
    ConversationSimplification,
    EmotionSummary,
    MemoryReminder,
    PromptBubbleSuggestion,
    RelationshipSummary,
    TimelineSummary,
    VocabularyAssistance,
)
from services.movie_knowledge_graph import MovieKnowledgeGraph

logger = logging.getLogger(__name__)


class AccessibilityReasoningEngine(AccessibilityReasoner):
    """Uses profiles and exact stored facts; it never predicts facts that knowledge does not contain."""

    def reason(self, request: AccessibilityReasoningRequest) -> AccessibilityReasoningResult:
        started = perf_counter()
        logger.info(
            "[TRACE][REASONING] start input scene_id=%s knowledge_characters=%d visible_entities=%d preferred_prompt_types=%s",
            request.current_scene.scene_id,
            len(request.knowledge.characters),
            len(next((scene.visible_entities for scene in request.knowledge.scene_summaries if scene.scene_id == request.current_scene.scene_id), [])),
            request.accessibility_profile.preferred_prompt_types,
        )
        limit = _detail_limit(request.accessibility_profile.detail_level)
        needs = {_normalize(need) for need in request.accessibility_profile.accessibility_needs}
        graph = MovieKnowledgeGraph(request.knowledge)
        scene_summary = graph.scene(request.current_scene.scene_id, request.timestamp_seconds)
        current_summary = request.current_scene.summary or (scene_summary.summary if scene_summary else "")
        cards = self._character_cards(request, limit)
        relationships = self._relationships(request, cards, limit)
        timeline = self._timeline(request, graph)
        emotions = self._emotions(request, limit)
        reminders = self._memory_reminders(request, limit)
        vocabulary = self._vocabulary(request, limit)
        conversations = self._conversations(request, limit)
        confusions = self._confusions(needs, cards, relationships, timeline, emotions, vocabulary, conversations)
        prompts = self._prompts(scene_summary, needs, cards, relationships, timeline, emotions, vocabulary, limit, request.accessibility_profile.preferred_prompt_types)
        # This is prepared, factual UI data rather than an opt-in explanation.
        # Profile settings still tailor depth and confusion predictions, but an
        # empty profile must not leave the ready prompt panel and visual drawer
        # blank after preparation has completed.
        drawer = AccessibilityDrawerContent(
            character_cards=cards,
            relationship_summaries=relationships,
            timeline_summary=timeline,
            emotion_summaries=emotions,
            memory_reminders=reminders,
            vocabulary_assistance=vocabulary if request.accessibility_profile.vocabulary_assistance else [],
            conversation_simplifications=conversations if request.accessibility_profile.conversation_simplification else [],
        )
        result = AccessibilityReasoningResult(
            companion_tone=f"{request.companion_profile.personality}; {request.companion_profile.conversation_style}",
            scene_summary=current_summary,
            likely_confusions=confusions,
            prompt_bubbles=prompts,
            drawer=drawer,
        )
        logger.info(
            "[TRACE][REASONING] complete output character_cards=%d relationships=%d timeline=%s emotions=%d reminders=%d prompts=%d prompt_list_id=%s first_prompt=%s duration_ms=%.1f",
            len(cards), len(relationships), timeline is not None, len(emotions), len(reminders), len(prompts), id(prompts),
            prompts[0].label if prompts else None, (perf_counter() - started) * 1000,
        )
        return result

    def _character_cards(self, request: AccessibilityReasoningRequest, limit: int) -> list[CharacterCard]:
        character_ids = set(request.current_scene.character_ids)
        characters = [character for character in request.knowledge.characters if not character_ids or character.id in character_ids]
        cards = [
            CharacterCard(
                character_id=character.id,
                name=character.name,
                reminder=f"{character.name} is a known character in this movie.",
                confidence=character.confidence,
                visual_anchor=next((anchor for anchor in request.knowledge.visual_anchors if anchor.semantic_id == character.id and (anchor.scene_id in {None, request.current_scene.scene_id})), None),
            )
            for character in characters[:limit]
        ]
        if cards:
            return cards

        # Unenrolled people and animals are still real semantic graph entities.
        # Expose them as observed scene subjects without assigning a movie
        # identity; this lets the visual drawer faithfully reflect perception.
        scene = _scene_for(request)
        if not scene:
            return []
        return [
            CharacterCard(
                character_id=entity.semantic_id or entity.id,
                name=entity.label.replace("_", " ").title(),
                reminder=f"The {entity.label} is visible in this scene.",
                confidence=entity.confidence,
                visual_anchor={
                    "id": f"observed-{entity.id}",
                    "semantic_id": entity.semantic_id or entity.id,
                    "scene_id": scene.scene_id,
                    "timestamp_seconds": scene.start_seconds,
                    "bbox": entity.bbox,
                    "confidence": entity.confidence,
                } if entity.bbox else None,
            )
            for entity in scene.visible_entities
            if entity.category in {"person", "animal"}
        ][:limit]

    def _relationships(self, request: AccessibilityReasoningRequest, cards: list[CharacterCard], limit: int) -> list[RelationshipSummary]:
        known_ids = {card.character_id for card in cards}
        relationships = [relationship for relationship in request.knowledge.relationships if not known_ids or {relationship.from_character_id, relationship.to_character_id}.issubset(known_ids)]
        confidence_by_id = {character.id: character.confidence for character in request.knowledge.characters}
        summaries = [
            RelationshipSummary(
                relationship_id=relationship.id,
                summary=relationship.description,
                confidence=min(confidence_by_id.get(relationship.from_character_id, 0.0), confidence_by_id.get(relationship.to_character_id, 0.0)),
            )
            for relationship in relationships[:limit]
        ]
        if summaries:
            return summaries

        # Florence interactions persisted on the exact scene are relationship
        # evidence, not an inferred character relationship. Keep that
        # distinction in the ID while making the factual drawer content usable.
        scene = _scene_for(request)
        if not scene:
            return []
        return [
            RelationshipSummary(
                relationship_id=f"{scene.scene_id}:interaction:{index}",
                summary=interaction,
                confidence=scene.confidence,
            )
            for index, interaction in enumerate(scene.interactions)
        ][:limit]

    def _timeline(self, request: AccessibilityReasoningRequest, graph: MovieKnowledgeGraph) -> TimelineSummary | None:
        position = graph.timeline_position(request.timestamp_seconds)
        return TimelineSummary(summary=position.description, confidence=request.knowledge.confidence) if position else None

    def _emotions(self, request: AccessibilityReasoningRequest, limit: int) -> list[EmotionSummary]:
        character_names = {character.id: character.name for character in request.knowledge.characters}
        return [
            EmotionSummary(
                emotion_id=emotion.id,
                summary=f"{character_names.get(emotion.character_id, 'Someone')} feels {emotion.emotion}.",
                confidence=emotion.confidence,
            )
            for emotion in request.knowledge.emotions
            if emotion.scene_id in {None, request.current_scene.scene_id}
        ][:limit]

    def _memory_reminders(self, request: AccessibilityReasoningRequest, limit: int) -> list[MemoryReminder]:
        prior = [item for item in request.knowledge.observation_history if item.timestamp_seconds < request.timestamp_seconds]
        return [MemoryReminder(summary=f"Earlier, you saw {item.entity_label}.", confidence=item.confidence) for item in prior[-limit:]]

    def _vocabulary(self, request: AccessibilityReasoningRequest, limit: int) -> list[VocabularyAssistance]:
        entries = [entry for entry in request.knowledge.vocabulary if not entry.scene_ids or request.current_scene.scene_id in entry.scene_ids]
        return [VocabularyAssistance(term=entry.term, simple_definition=entry.simple_definition, confidence=entry.confidence) for entry in entries[:limit]]

    def _conversations(self, request: AccessibilityReasoningRequest, limit: int) -> list[ConversationSimplification]:
        active = [dialogue for dialogue in request.knowledge.dialogue if dialogue.start_seconds <= request.timestamp_seconds <= dialogue.end_seconds]
        return [ConversationSimplification(dialogue_id=item.id, simple_text=item.text, confidence=item.confidence) for item in active[:limit]]

    def _confusions(self, needs, cards, relationships, timeline, emotions, vocabulary, conversations) -> list[ConfusionPrediction]:
        predictions: list[ConfusionPrediction] = []
        if cards and _needs(needs, "remember characters", "characters"):
            predictions.append(ConfusionPrediction(kind="character_memory", confidence=max(card.confidence for card in cards), reason="Known characters are present in the current context."))
        if relationships and _needs(needs, "relationships"):
            predictions.append(ConfusionPrediction(kind="relationship", confidence=max(item.confidence for item in relationships), reason="Known character relationships are relevant."))
        if timeline and _needs(needs, "plot", "timeline"):
            predictions.append(ConfusionPrediction(kind="timeline", confidence=timeline.confidence, reason="A verified timeline position is available."))
        if emotions and _needs(needs, "emotions", "understand emotions"):
            predictions.append(ConfusionPrediction(kind="emotion", confidence=max(item.confidence for item in emotions), reason="Verified emotion knowledge is available."))
        if vocabulary:
            predictions.append(ConfusionPrediction(kind="vocabulary", confidence=max(item.confidence for item in vocabulary), reason="Scene vocabulary assistance is available."))
        if conversations and _needs(needs, "conversations", "conversation"):
            predictions.append(ConfusionPrediction(kind="conversation", confidence=max(item.confidence for item in conversations), reason="Current dialogue can be shown in simpler form."))
        return predictions

    def _prompts(self, scene_summary, needs, cards, relationships, timeline, emotions, vocabulary, limit: int, preferred: list[str]) -> list[PromptBubbleSuggestion]:
        """Offer only questions grounded in entities/actions stored for this exact scene."""
        prompts: list[PromptBubbleSuggestion] = []
        visible = scene_summary.visible_entities if scene_summary and scene_summary.prepared else []
        visible_people = [entity for entity in visible if entity.category in {"person", "animal"}]
        visible_objects = [entity for entity in visible if entity.category == "object"]
        if cards and visible_people:
            prompts.append(PromptBubbleSuggestion(id="visible-character", kind="character", label="Who is that?", question=f"Who is {cards[0].name}?", priority=1))
        elif visible_people:
            label = visible_people[0].label
            prompts.append(PromptBubbleSuggestion(id="visible-person", kind="visible_entity", label="Who is that?", question=f"What is the {label} doing?", priority=1))
        if relationships and len(cards) > 1:
            prompts.append(PromptBubbleSuggestion(id="relationship", kind="relationship", label="How are they connected?", question="How are these characters connected?", priority=2))
        if emotions and visible_people:
            prompts.append(PromptBubbleSuggestion(id="emotion", kind="emotion", label="How do they feel?", question="How does this person feel?", priority=3))
        if scene_summary and scene_summary.actions:
            prompts.append(PromptBubbleSuggestion(id="visible-action", kind="scene", label="What is happening?", question="What is happening in this scene?", priority=4))
        if visible_objects:
            prompts.append(PromptBubbleSuggestion(id="visible-object", kind="object", label="What is that?", question=f"What is the {visible_objects[0].label}?", priority=5))
        if vocabulary and scene_summary and scene_summary.prepared:
            prompts.append(PromptBubbleSuggestion(id="vocabulary", kind="vocabulary", label="What does that mean?", question=f"What does {vocabulary[0].term} mean?", priority=5))
        if preferred:
            allowed_kinds = _preferred_prompt_kinds(preferred)
            # Onboarding stores user-facing intents (for example "character
            # introduction"), not the engine's internal prompt kind.  Only
            # apply a filter when an intent maps to a real generated kind;
            # otherwise preserve the evidence-backed prompts.
            if allowed_kinds:
                prompts = [prompt for prompt in prompts if _normalize(prompt.kind) in allowed_kinds]
        logger.info(
            "[TRACE][PROMPTS] executed visible_people=%d visible_objects=%d cards=%d actions=%d generated=%d prompt_list_id=%s first_prompt=%s preferred=%s",
            len(visible_people), len(visible_objects), len(cards), len(scene_summary.actions) if scene_summary else 0,
            len(prompts), id(prompts), prompts[0].label if prompts else None, preferred,
        )
        return prompts[:limit]


def _detail_limit(detail_level: str) -> int:
    level = _normalize(detail_level)
    return 6 if any(term in level for term in ("more", "detailed", "full")) else 2


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").split())


def _needs(needs: set[str], *terms: str) -> bool:
    return any(_normalize(term) in needs for term in terms)


def _preferred_prompt_kinds(preferred: list[str]) -> set[str]:
    """Translate persisted onboarding intents to the reasoner's real prompt kinds."""
    mapped = {
        "character introduction": {"character", "visible entity"},
        "relationship update": {"relationship"},
        "emotion insight": {"emotion"},
        "scene summary": {"scene"},
        "important event": {"scene"},
        "visual scene explanation": {"scene"},
        "important object": {"object"},
        "word explanation": {"vocabulary"},
        "conversation summary": {"conversation"},
    }
    engine_kinds = {"character", "visible entity", "relationship", "emotion", "scene", "object", "vocabulary", "conversation"}
    allowed: set[str] = set()
    for item in preferred:
        normalized = _normalize(item)
        allowed.update(mapped.get(normalized, set()))
        if normalized in engine_kinds:
            allowed.add(normalized)
    return allowed


def _scene_for(request: AccessibilityReasoningRequest):
    return next(
        (scene for scene in request.knowledge.scene_summaries if scene.scene_id == request.current_scene.scene_id),
        None,
    )
