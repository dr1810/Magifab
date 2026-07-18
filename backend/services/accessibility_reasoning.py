"""Graph-only accessibility reasoning; raw perception is deliberately inaccessible here."""
import logging
from time import perf_counter

from models.accessibility_reasoner import AccessibilityReasoner
from schemas.accessibility_presentation import AccessibilityPresentation
from schemas.accessibility_reasoning import (
    AccessibilityReasoningRequest,
    CharacterCard,
    ConversationSimplification,
    EmotionSummary,
    MemoryReminder,
    PromptBubbleSuggestion,
    RelationshipSummary,
    TimelineSummary,
    VocabularyAssistance,
)

logger = logging.getLogger(__name__)


class AccessibilityReasoningEngine(AccessibilityReasoner):
    """The sole producer of user-facing content, from semantic claims only."""

    def reason(self, request: AccessibilityReasoningRequest) -> AccessibilityPresentation:
        started = perf_counter()
        context = request.context
        profile = context.accessibility_profile
        limit = _detail_limit(profile.detail_level)
        logger.info(
            "[TRACE][REASONING] start movie=%s scene=%s semantic_claims=%d active_characters=%d raw_perception=unavailable",
            context.movie_id, context.scene_id, len(context.semantic_scene), len(context.active_characters),
        )
        cards = self._character_cards(context, limit)
        relationships = self._relationships(context, limit)
        timeline = self._timeline(context)
        emotions = self._emotions(context, limit)
        reminders = self._memory_reminders(context, limit)
        vocabulary = self._vocabulary(context, limit)
        conversations = self._conversations(context, limit)
        prompts = self._prompts(context, cards, relationships, timeline, emotions, vocabulary, limit, profile.preferred_prompt_types)
        result = AccessibilityPresentation(
            scene_explanation=_scene_summary(context),
            prompt_bubbles=prompts,
            character_cards=cards,
            relationship_summaries=relationships,
            timeline_summary=timeline,
            emotion_summaries=emotions,
            memory_reminders=reminders,
            vocabulary_assistance=vocabulary if profile.vocabulary_assistance else [],
            conversation_simplifications=conversations if profile.conversation_simplification else [],
        )
        logger.info(
            "[TRACE][REASONING] complete cards=%d relationships=%d timeline=%s emotions=%d reminders=%d prompts=%d duration_ms=%.1f",
            len(cards), len(relationships), timeline is not None, len(emotions), len(reminders), len(prompts),
            (perf_counter() - started) * 1000,
        )
        return result

    @staticmethod
    def _character_cards(context, limit: int) -> list[CharacterCard]:
        return [
            CharacterCard(
                character_id=entity.id,
                name=entity.name,
                reminder=_character_reminder(context, entity),
                confidence=entity.confidence,
                visual_anchor=None,
                claim_ids=entity.claim_ids,
            )
            for entity in context.active_characters[:limit]
        ]

    @staticmethod
    def _relationships(context, limit: int) -> list[RelationshipSummary]:
        return [
            RelationshipSummary(
                relationship_id=item.id,
                summary=item.description,
                confidence=item.confidence,
                claim_ids=item.claim_ids,
            )
            for item in context.relationships[:limit]
        ]

    @staticmethod
    def _timeline(context) -> TimelineSummary | None:
        if not context.timeline or not context.timeline_claim_ids:
            return None
        return TimelineSummary(
            summary=context.timeline.description,
            confidence=1.0,
            claim_ids=context.timeline_claim_ids,
        )

    @staticmethod
    def _emotions(context, limit: int) -> list[EmotionSummary]:
        return [
            EmotionSummary(
                emotion_id=claim.id,
                summary=claim.value,
                confidence=claim.confidence,
                claim_ids=[claim.id],
            )
            for claim in context.emotion_claims[:limit]
            if claim.value
        ]

    @staticmethod
    def _memory_reminders(context, limit: int) -> list[MemoryReminder]:
        return [
            MemoryReminder(
                summary=_event_summary(claim), confidence=claim.confidence, claim_ids=[claim.id],
            )
            for claim in context.previous_events[-limit:]
        ]

    @staticmethod
    def _vocabulary(context, limit: int) -> list[VocabularyAssistance]:
        return [
            VocabularyAssistance(
                term=claim.subject_id,
                simple_definition=claim.value,
                confidence=claim.confidence,
                claim_ids=[claim.id],
            )
            for claim in context.vocabulary_claims[:limit]
            if claim.value
        ]

    @staticmethod
    def _conversations(context, limit: int) -> list[ConversationSimplification]:
        return [
            ConversationSimplification(
                dialogue_id=claim.id,
                simple_text=claim.value,
                confidence=claim.confidence,
                claim_ids=[claim.id],
            )
            for claim in context.conversation_claims[:limit]
            if claim.value
        ]

    def _prompts(self, context, cards, relationships, timeline, emotions, vocabulary, limit: int, preferred: list[str]) -> list[PromptBubbleSuggestion]:
        prompts: list[PromptBubbleSuggestion] = []
        if cards:
            card = cards[0]
            appeared_before = any(
                claim.kind == "character_present" and claim.subject_id == card.character_id
                for claim in context.previous_character_presence
            )
            label = "Why are they important?" if appeared_before else "Who is this character?"
            question = f"Why is {card.name} important now?" if appeared_before else f"Who is {card.name}?"
            prompts.append(PromptBubbleSuggestion(
                id=f"character-{card.character_id}", kind="character", label=label, question=question,
                priority=1, claim_ids=card.claim_ids,
            ))
        event = next((claim for claim in context.semantic_scene if claim.kind in {"event", "timeline_change"}), None)
        if event:
            prompts.append(PromptBubbleSuggestion(
                id=f"event-{event.id}", kind="scene", label="What just changed?",
                question="What changed in this scene, and why does it matter?", priority=2, claim_ids=[event.id],
            ))
        if relationships:
            item = relationships[0]
            prompts.append(PromptBubbleSuggestion(
                id=f"relationship-{item.relationship_id}", kind="relationship", label="How are they connected?",
                question="How are these characters connected?", priority=3, claim_ids=item.claim_ids,
            ))
        if timeline:
            prompts.append(PromptBubbleSuggestion(
                id="timeline-current", kind="timeline", label="Where are we in the story?",
                question="How does this moment connect to earlier events?", priority=4, claim_ids=timeline.claim_ids,
            ))
        if emotions:
            item = emotions[0]
            prompts.append(PromptBubbleSuggestion(
                id=f"emotion-{item.emotion_id}", kind="emotion", label="How do they feel?",
                question="What feeling is important in this moment?", priority=5, claim_ids=item.claim_ids,
            ))
        if vocabulary:
            item = vocabulary[0]
            prompts.append(PromptBubbleSuggestion(
                id=f"vocabulary-{item.term}", kind="vocabulary", label="What does that mean?",
                question=f"What does {item.term} mean here?", priority=6, claim_ids=item.claim_ids,
            ))
        allowed = _preferred_prompt_kinds(preferred)
        if allowed:
            prompts = [item for item in prompts if _normalize(item.kind) in allowed]
        return prompts[:limit]

def _scene_summary(context) -> str:
    state = next((claim for claim in context.semantic_scene if claim.kind == "scene_state" and claim.value), None)
    return state.value if state else "No semantic scene state is available."


def _character_reminder(context, entity) -> str:
    appeared_before = any(claim.subject_id == entity.id for claim in context.previous_character_presence)
    return f"{entity.name} appeared earlier in this movie." if appeared_before else f"{entity.name} is important in this scene."


def _event_summary(claim) -> str:
    return claim.value or "An earlier semantic event remains relevant."


def _detail_limit(detail_level: str) -> int:
    return 6 if any(term in _normalize(detail_level) for term in ("more", "detailed", "full")) else 2


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").split())


def _preferred_prompt_kinds(preferred: list[str]) -> set[str]:
    mapped = {
        "character introduction": {"character"}, "relationship update": {"relationship"},
        "emotion insight": {"emotion"}, "scene summary": {"scene"},
        "important event": {"scene"}, "visual scene explanation": {"scene"},
        "word explanation": {"vocabulary"}, "conversation summary": {"conversation"},
    }
    return {kind for item in preferred for kind in mapped.get(_normalize(item), {_normalize(item)} if _normalize(item) in {"character", "relationship", "emotion", "scene", "timeline", "vocabulary", "conversation"} else set())}
