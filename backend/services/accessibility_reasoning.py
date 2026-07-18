"""Deterministic accessibility content generation from verified Semantic Movie Knowledge."""
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


class AccessibilityReasoningEngine(AccessibilityReasoner):
    """Uses profiles and exact stored facts; it never predicts facts that knowledge does not contain."""

    def reason(self, request: AccessibilityReasoningRequest) -> AccessibilityReasoningResult:
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
        drawer = AccessibilityDrawerContent(
            character_cards=cards if _needs(needs, "remember characters", "characters") else [],
            relationship_summaries=relationships if _needs(needs, "relationships") else [],
            timeline_summary=timeline if _needs(needs, "plot", "timeline") else None,
            emotion_summaries=emotions if _needs(needs, "emotions", "understand emotions") else [],
            memory_reminders=reminders if _needs(needs, "remember characters", "memory") else [],
            vocabulary_assistance=vocabulary if request.accessibility_profile.vocabulary_assistance else [],
            conversation_simplifications=conversations if request.accessibility_profile.conversation_simplification else [],
        )
        return AccessibilityReasoningResult(
            companion_tone=f"{request.companion_profile.personality}; {request.companion_profile.conversation_style}",
            scene_summary=current_summary,
            likely_confusions=confusions,
            prompt_bubbles=prompts,
            drawer=drawer,
        )

    def _character_cards(self, request: AccessibilityReasoningRequest, limit: int) -> list[CharacterCard]:
        character_ids = set(request.current_scene.character_ids)
        characters = [character for character in request.knowledge.characters if not character_ids or character.id in character_ids]
        return [
            CharacterCard(
                character_id=character.id,
                name=character.name,
                reminder=f"{character.name} is a known character in this movie.",
                confidence=character.confidence,
                visual_anchor=next((anchor for anchor in request.knowledge.visual_anchors if anchor.semantic_id == character.id and (anchor.scene_id in {None, request.current_scene.scene_id})), None),
            )
            for character in characters[:limit]
        ]

    def _relationships(self, request: AccessibilityReasoningRequest, cards: list[CharacterCard], limit: int) -> list[RelationshipSummary]:
        known_ids = {card.character_id for card in cards}
        relationships = [relationship for relationship in request.knowledge.relationships if not known_ids or {relationship.from_character_id, relationship.to_character_id}.issubset(known_ids)]
        confidence_by_id = {character.id: character.confidence for character in request.knowledge.characters}
        return [
            RelationshipSummary(
                relationship_id=relationship.id,
                summary=relationship.description,
                confidence=min(confidence_by_id.get(relationship.from_character_id, 0.0), confidence_by_id.get(relationship.to_character_id, 0.0)),
            )
            for relationship in relationships[:limit]
        ]

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
        if cards and visible_people and _needs(needs, "remember characters", "characters"):
            prompts.append(PromptBubbleSuggestion(id="visible-character", kind="character", label="Who is that?", question=f"Who is {cards[0].name}?", priority=1))
        elif visible_people and _needs(needs, "remember characters", "characters"):
            label = visible_people[0].label
            prompts.append(PromptBubbleSuggestion(id="visible-person", kind="visible_entity", label="Who is that?", question=f"What is the {label} doing?", priority=1))
        if relationships and len(cards) > 1 and _needs(needs, "relationships"):
            prompts.append(PromptBubbleSuggestion(id="relationship", kind="relationship", label="How are they connected?", question="How are these characters connected?", priority=2))
        if emotions and visible_people and _needs(needs, "emotions", "understand emotions"):
            prompts.append(PromptBubbleSuggestion(id="emotion", kind="emotion", label="How do they feel?", question="How does this person feel?", priority=3))
        if scene_summary and scene_summary.actions and _needs(needs, "plot", "timeline"):
            prompts.append(PromptBubbleSuggestion(id="visible-action", kind="scene", label="What is happening?", question="What is happening in this scene?", priority=4))
        if visible_objects:
            prompts.append(PromptBubbleSuggestion(id="visible-object", kind="object", label="What is that?", question=f"What is the {visible_objects[0].label}?", priority=5))
        if vocabulary and scene_summary and scene_summary.prepared:
            prompts.append(PromptBubbleSuggestion(id="vocabulary", kind="vocabulary", label="What does that mean?", question=f"What does {vocabulary[0].term} mean?", priority=5))
        if preferred:
            preferred_set = {_normalize(item) for item in preferred}
            prompts = [prompt for prompt in prompts if _normalize(prompt.kind) in preferred_set]
        return prompts[:limit]


def _detail_limit(detail_level: str) -> int:
    level = _normalize(detail_level)
    return 6 if any(term in level for term in ("more", "detailed", "full")) else 2


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").split())


def _needs(needs: set[str], *terms: str) -> bool:
    return any(_normalize(term) in needs for term in terms)
