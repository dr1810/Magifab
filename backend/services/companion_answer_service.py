"""Whole-work retrieval and structured LLM answer assembly."""
from __future__ import annotations

from dataclasses import asdict
import logging

from models.answer_generator import AnswerGenerator
from schemas.companion_pipeline import CompanionPipelineRequest
from schemas.interval_state import CompanionAnswer, CompanionDebugIssue, CompanionDebugTrace, ConversationContext, IntervalPrompts, IntervalState, PromptAnswer, VisualDrawerState
from services.conversation_memory import ConversationMemory
from services.interval_state_store import IntervalStateRepository
from services.intent_router import IntentRoute, SemanticIntentRouter
from services.semantic_retrieval import SemanticRetrievalIndex

logger = logging.getLogger(__name__)


class CompanionAnswerService:
    """Retrieves bounded whole-work evidence before any LLM generation."""

    def __init__(self, states: IntervalStateRepository, generator: AnswerGenerator, memory: ConversationMemory | None = None, semantic_index: SemanticRetrievalIndex | None = None, intent_router: SemanticIntentRouter | None = None, debug_enabled: bool = False) -> None:
        self._states = states
        self._generator = generator
        self._memory = memory or ConversationMemory()
        if semantic_index is None:
            raise ValueError("semantic_index_required")
        if intent_router is None:
            raise ValueError("intent_router_required")
        self._semantic_index = semantic_index
        self._intent_router = intent_router
        self._debug_enabled = debug_enabled

    def preprocess_work(self, work_id: str) -> None:
        """Embed the complete prepared work once; requests never construct an index."""
        self._semantic_index.build(work_id, self._states.list_movie_states(work_id))

    def answer(self, request: CompanionPipelineRequest, current: IntervalState) -> IntervalState:
        all_states = self._states.list_movie_states(request.movie_id)
        memory_key = f"{request.movie_id}:{request.conversation_id}"
        conversation = [asdict(turn) for turn in self._memory.recall(memory_key)]
        route = self._intent_router.route(request.question)
        context, retrieval_debug = self._retrieve(request, current, all_states, route, conversation)
        payload = {
            "question": request.question,
            "personal_memory": self._personal_memory(request),
            "intent_route": {"intent": route.intent, "evidence_kinds": route.evidence_kinds, "retrieval_instruction": route.retrieval_instruction},
            "conversation_memory": conversation,
            "retrieval_context": context,
        }
        if self._debug_enabled:
            generated_payload, exact_prompt, raw_response = self._generator.generate_with_trace(payload)
        else:
            generated_payload, exact_prompt, raw_response = self._generator.generate(payload), "", ""
        generated = self._validated(generated_payload)
        answer = CompanionAnswer(**generated)
        self._memory.remember(memory_key, request.question, answer.answer)
        drawer = VisualDrawerState(
            now=answer.answer,
            who=answer.entities,
            relationships=answer.relationships,
            timeline=answer.timeline_references,
            next=answer.suggested_follow_up_prompts[0] if answer.suggested_follow_up_prompts else None,
            word_count=min(120, len(answer.answer.split())),
            story_now=(answer.answer,),
            memory=tuple(turn["question"] for turn in context["conversation_memory"]),
        )
        prompts = IntervalPrompts(
            prompt_bubbles=current.prompts.prompt_bubbles,
            prompt_answers=(PromptAnswer(prompt_id=request.question, question=request.question, answer=answer.answer),),
            suggested_questions=answer.suggested_follow_up_prompts,
        )
        answered = current.model_copy(update={
            "companionAnswer": answer,
            "prompts": prompts,
            "visualDrawer": drawer,
            "conversationContext": ConversationContext(scene_explanation=answer.answer),
        })
        if self._debug_enabled:
            trace = self._debug_trace(request, current, context, retrieval_debug, exact_prompt, raw_response, generated, answered)
            logger.info("[COMPANION_DEBUG_TRACE] %s", trace.model_dump_json())
            answered = answered.model_copy(update={"companionDebug": trace})
        return answered

    def _retrieve(self, request: CompanionPipelineRequest, current: IntervalState, all_states: list[IntervalState], route: IntentRoute, conversation: list[dict[str, str]]) -> tuple[dict[str, object], dict[str, object]]:
        query_terms = [request.question, route.retrieval_instruction]
        all_entities = _unique_text(name for state in all_states for name in [*(card.name for card in state.characters), *state.semanticMemoryAfter.active_characters])
        seeds = [entity for entity in all_entities if any(entity.casefold() in term.casefold() for term in query_terms)]
        if self._debug_enabled:
            scored = self._semantic_index.retrieve_with_scores(request.movie_id, " ".join(query_terms), current_interval_id=current.metadata.interval_id, allowed_kinds=route.evidence_kinds, entity_hints=tuple(seeds))
            chunks = [item.chunk for item in scored]
            retrieval_debug = {"semantic_query": " ".join(query_terms), "intent": route.intent, "allowed_kinds": route.evidence_kinds, "top_chunks": [{"chunk_id": item.chunk.id, "kind": item.chunk.kind, "similarity_score": item.similarity_score, "source": item.chunk.source, "start_time": item.chunk.start_time, "end_time": item.chunk.end_time, "text": item.chunk.text} for item in scored[:5]]}
        else:
            chunks = self._semantic_index.retrieve(request.movie_id, " ".join(query_terms), current_interval_id=current.metadata.interval_id, allowed_kinds=route.evidence_kinds, entity_hints=tuple(seeds))
            retrieval_debug = {}
        context = {
            "evidence_chunks": [{"id": chunk.id, "kind": chunk.kind, "text": chunk.text, "source": chunk.source, "start_time": chunk.start_time, "end_time": chunk.end_time, "entities": chunk.entities, "relationships": chunk.relationships} for chunk in chunks],
            "retrieval_trace": {"intent": route.intent, "allowed_evidence_kinds": route.evidence_kinds, "entity_seeds": seeds, "chunk_count": len(chunks)},
            "conversation_memory": conversation,
        }
        return context, retrieval_debug

    def _debug_trace(self, request, current, context, retrieval, prompt, raw_response, parsed, answered) -> CompanionDebugTrace:
        source = current.sourceContext
        current_context = {
            "content_id": request.movie_id,
            "timestamp_seconds": request.timestamp_seconds,
            "scene_id": current.storyState.current_interval_id,
            "chunk_id": current.metadata.interval_id,
            "characters_detected": [card.name for card in current.characters],
            "subtitle": source.subtitle if source else None,
            "current_page": {"start": source.page_start, "end": source.page_end} if source and source.page_start else None,
            "visible_text": source.visible_text if source else None,
        }
        issues = []
        if not retrieval.get("top_chunks"):
            issues.append(CompanionDebugIssue(stage="STEP 2 Retrieval", message="No route-approved evidence chunks matched. The answer is necessarily evidence-limited."))
        if current_context["visible_text"] is None:
            issues.append(CompanionDebugIssue(stage="STEP 1 Current Context", message="Raw visible text is not persisted in the prepared interval; this field is unavailable."))
        final_ui = {"companionAnswer": answered.companionAnswer.model_dump(mode="json") if answered.companionAnswer else None, "visualDrawer": answered.visualDrawer.model_dump(mode="json"), "prompts": answered.prompts.model_dump(mode="json"), "conversationContext": answered.conversationContext.model_dump(mode="json")}
        return CompanionDebugTrace(user_question=request.question, current_context=current_context, retrieval=retrieval, prompt=prompt, gemini_response=raw_response, parsed_json=parsed, formatted_response=answered.companionAnswer.model_dump(mode="json") if answered.companionAnswer else {}, final_ui=final_ui, issues=tuple(issues))

    @staticmethod
    def _personal_memory(request: CompanionPipelineRequest) -> dict[str, object]:
        accessibility = request.accessibility_profile.model_dump(mode="json")
        companion = request.companion_profile.model_dump(mode="json")
        return {"learning_preferences": accessibility, "companion_preferences": companion}

    @staticmethod
    def _validated(payload: dict[str, object]) -> dict[str, object]:
        required = {"answer", "intent", "visual_aid_type", "entities", "relationships", "timeline_references", "suggested_follow_up_prompts"}
        if not required.issubset(payload) or not isinstance(payload["answer"], str) or not payload["answer"].strip():
            raise ValueError("invalid_grounded_answer")
        return {key: payload[key] for key in required}


def _state_text(state: IntervalState) -> str:
    return " ".join(filter(None, [state.storyState.scene_summary, state.conversationContext.scene_explanation, *state.storyState.story_so_far, *state.semanticMemoryAfter.story_events, *state.semanticMemoryAfter.active_characters, *state.semanticMemoryAfter.relationships]))


def _state_evidence(state: IntervalState) -> dict[str, object]:
    return {
        "interval_id": state.metadata.interval_id,
        "start_time": state.metadata.start_time,
        "end_time": state.metadata.end_time,
        "summary": state.storyState.scene_summary,
        "events": state.semanticMemoryAfter.story_events,
        "characters": [card.name for card in state.characters],
        "relationships": [item.summary for item in state.relationships],
        "objects": state.semanticMemoryAfter.important_objects,
        "conversation": state.conversationContext.scene_explanation,
    }


def _timeline_evidence(state: IntervalState) -> dict[str, object]:
    return {"interval_id": state.metadata.interval_id, "start_time": state.metadata.start_time, "event": state.timelineMemory.current_event or state.storyState.scene_summary}


def _entity_memory(entity: str, states: list[IntervalState]) -> dict[str, object]:
    appearances = [state for state in states if entity.casefold() in _state_text(state).casefold()]
    return {
        "entity": entity,
        "first_appearance": _timeline_evidence(appearances[0]) if appearances else None,
        "latest_appearance": _timeline_evidence(appearances[-1]) if appearances else None,
        "important_events": [state.storyState.scene_summary for state in appearances if state.storyState.scene_summary],
        "relationship_history": _unique_text(value for state in appearances for value in [*(item.summary for item in state.relationships), *state.semanticMemoryAfter.relationships]),
    }


def _unique_states(states: list[IntervalState], limit: int) -> list[IntervalState]:
    result: list[IntervalState] = []
    seen: set[str] = set()
    for state in states:
        if state.metadata.interval_id not in seen:
            seen.add(state.metadata.interval_id)
            result.append(state)
        if len(result) == limit:
            break
    return result


def _unique_text(values) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            result.append(value)
    return result
