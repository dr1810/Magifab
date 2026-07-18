"""Graph-only accessibility reasoning; raw perception is deliberately inaccessible here."""
import logging
from time import perf_counter
from threading import Lock
from dataclasses import dataclass

from config import get_settings
from services.semantic_claim_audit import log_claims
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

    def __init__(self, cooldown_seconds: float | None = None):
        self._cooldown_seconds = get_settings().semantic_prompt_cooldown_seconds if cooldown_seconds is None else cooldown_seconds
        self._prompt_history: dict[tuple[str, str], float] = {}
        self._prompt_lock = Lock()

    def reason(self, request: AccessibilityReasoningRequest) -> AccessibilityPresentation:
        started = perf_counter()
        context = request.context
        log_claims("AccessibilityReasoningEngine.input", context.semantic_scene, movie_id=context.movie_id, scene_id=context.scene_id)
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
        prompts = self._prompts(context, limit, profile.preferred_prompt_types)
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

    def _prompts(self, context, limit: int, preferred: list[str]) -> list[PromptBubbleSuggestion]:
        """Prioritize graph claims, never cards or raw perception, into prompts."""
        candidates = _prompt_candidates(context)
        allowed = _preferred_prompt_kinds(preferred)
        if allowed:
            candidates = [item for item in candidates if _normalize(item.prompt.kind) in allowed]
        prompts: list[PromptBubbleSuggestion] = []
        seen: set[str] = set()
        for candidate in sorted(candidates, key=lambda item: (item.prompt.priority, item.prompt.id)):
            if candidate.key in seen or self._in_cooldown(context.movie_id, candidate.key, context.timestamp_seconds):
                continue
            seen.add(candidate.key)
            self._record_prompt(context.movie_id, candidate.key, context.timestamp_seconds)
            prompts.append(candidate.prompt)
            logger.info(
                "[TRACE][PROMPT] emitted=yes movie=%s key=%s priority=%d reason=%s claim_ids=%s",
                context.movie_id, candidate.key, candidate.prompt.priority, candidate.reason, candidate.prompt.claim_ids,
            )
            if len(prompts) == limit:
                break
        return prompts

    def _in_cooldown(self, movie_id: str, key: str, timestamp_seconds: float) -> bool:
        """Suppress the same semantic question on adjacent prepared frames."""
        history_key = (movie_id, key)
        with self._prompt_lock:
            previous = self._prompt_history.get(history_key)
        return previous is not None and 0 <= timestamp_seconds - previous < self._cooldown_seconds

    def _record_prompt(self, movie_id: str, key: str, timestamp_seconds: float) -> None:
        with self._prompt_lock:
            self._prompt_history[(movie_id, key)] = timestamp_seconds
            # Keep the small process-local map bounded per movie timeline.
            cutoff = timestamp_seconds - max(self._cooldown_seconds * 4, 30)
            self._prompt_history = {
                item: value for item, value in self._prompt_history.items()
                if item[0] != movie_id or value >= cutoff
            }


@dataclass(frozen=True)
class _PromptCandidate:
    key: str
    prompt: PromptBubbleSuggestion
    reason: str


def _prompt_candidates(context) -> list[_PromptCandidate]:
    """Apply the accessibility prompt policy exclusively to semantic claims."""
    claims = context.semantic_scene
    previous_character_ids = {claim.subject_id for claim in context.previous_character_presence}
    candidates: list[_PromptCandidate] = []

    # Priority 1: new identities, important story changes, and relationships.
    for claim in claims:
        if claim.kind == "character_present" and claim.subject_id not in previous_character_ids:
            entity = next((item for item in context.active_characters if item.id == claim.subject_id), None)
            if entity:
                candidates.append(_candidate(
                    key=f"character:{entity.id}", prompt_id=f"character-{entity.id}", kind="character",
                    label="Who is this character?", question=f"Who is {entity.name}?", priority=1,
                    claim_ids=_claim_ids(entity.claim_ids, claim.id), reason="newly_introduced_character",
                ))
        elif claim.kind == "event" and (claim.evidence_origin == "movie_knowledge_supported" or claim.knowledge_ids):
            candidates.append(_candidate(
                key=f"event:{claim.subject_id}", prompt_id=f"event-{claim.subject_id}", kind="scene",
                label="What just changed?", question="What changed in this moment, and why does it matter?", priority=1,
                claim_ids=[claim.id], reason="important_timeline_event",
            ))
        elif claim.kind == "relationship":
            candidates.append(_candidate(
                key=f"relationship:{claim.subject_id}", prompt_id=f"relationship-{claim.subject_id}", kind="relationship",
                label="Why does this connection matter?", question=claim.value or "Why does this relationship matter now?", priority=1,
                claim_ids=[claim.id], reason="relationship_change",
            ))

    # Priority 2: action ambiguity, callbacks, cross-scene references, emotion.
    for claim in claims:
        if claim.kind == "event" and claim.evidence_origin == "perception_verified" and claim.value:
            candidates.append(_candidate(
                key=f"action:{claim.subject_id}", prompt_id=f"action-{claim.subject_id}", kind="scene",
                label="What is happening?", question=f"What does '{claim.value}' mean in this scene?", priority=2,
                claim_ids=[claim.id], reason="confusing_action",
            ))
        elif claim.kind == "callback" and claim.predicate != "defines":
            candidates.append(_candidate(
                key=f"callback:{claim.subject_id}:{claim.predicate}", prompt_id=f"callback-{claim.id}", kind="scene",
                label="How does this connect?", question="How does this connect to an earlier part of the story?", priority=2,
                claim_ids=[claim.id], reason="callback_or_previous_scene_reference",
            ))
        elif claim.kind == "timeline_change" and _was_previously_seen(claim, context.previous_character_presence):
            candidates.append(_candidate(
                key=f"return:{claim.subject_id}", prompt_id=f"return-{claim.subject_id}", kind="timeline",
                label="Why are they back?", question="How does this connect to what happened earlier?", priority=2,
                claim_ids=[claim.id], reason="reference_to_previous_scene",
            ))
        elif claim.kind == "emotion" and claim.value:
            candidates.append(_candidate(
                key=f"emotion:{claim.subject_id}", prompt_id=f"emotion-{claim.subject_id}", kind="emotion",
                label="How do they feel?", question="What feeling is important in this moment?", priority=2,
                claim_ids=[claim.id], reason="emotional_change",
            ))

    # Priority 3: vocabulary help and a graph-derived visual scene explanation.
    for claim in claims:
        if claim.kind == "callback" and claim.predicate == "defines" and claim.value:
            candidates.append(_candidate(
                key=f"vocabulary:{claim.subject_id}", prompt_id=f"vocabulary-{claim.subject_id}", kind="vocabulary",
                label="What does that mean?", question=f"What does {claim.subject_id} mean here?", priority=3,
                claim_ids=[claim.id], reason="vocabulary_definition",
            ))
        elif claim.kind == "scene_state" and claim.value:
            candidates.append(_candidate(
                key=f"visual:{claim.scene_id}", prompt_id=f"visual-{claim.scene_id}", kind="scene",
                label="Explain this scene", question="What are the important details in this scene?", priority=3,
                claim_ids=[claim.id], reason="semantic_visual_explanation",
            ))
    return candidates


def _candidate(*, key: str, prompt_id: str, kind: str, label: str, question: str, priority: int, claim_ids: list[str], reason: str) -> _PromptCandidate:
    return _PromptCandidate(
        key=key,
        prompt=PromptBubbleSuggestion(id=prompt_id, kind=kind, label=label, question=question, priority=priority, claim_ids=list(dict.fromkeys(claim_ids))),
        reason=reason,
    )


def _claim_ids(existing: list[str], current: str) -> list[str]:
    return list(dict.fromkeys([*existing, current]))


def _was_previously_seen(claim, previous_claims) -> bool:
    return any(item.subject_id == claim.subject_id for item in previous_claims)

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
