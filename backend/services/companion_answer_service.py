"""Whole-work retrieval and structured LLM answer assembly."""
from __future__ import annotations

from dataclasses import asdict

from models.answer_generator import AnswerGenerator
from schemas.companion_pipeline import CompanionPipelineRequest
from schemas.interval_state import CompanionAnswer, ConversationContext, IntervalPrompts, IntervalState, PromptAnswer, VisualDrawerState
from services.conversation_memory import ConversationMemory
from services.interval_state_store import IntervalStateRepository
from knowledge_engine.embeddings import EmbeddingProvider, HashEmbeddingProvider, cosine_similarity


class CompanionAnswerService:
    """Retrieves bounded whole-work evidence before any LLM generation."""

    def __init__(self, states: IntervalStateRepository, generator: AnswerGenerator, memory: ConversationMemory | None = None, embeddings: EmbeddingProvider | None = None) -> None:
        self._states = states
        self._generator = generator
        self._memory = memory or ConversationMemory()
        self._embeddings = embeddings or HashEmbeddingProvider()

    def answer(self, request: CompanionPipelineRequest, current: IntervalState) -> IntervalState:
        all_states = self._states.list_movie_states(request.movie_id)
        context = self._retrieve(request, current, all_states)
        memory_key = f"{request.movie_id}:{request.conversation_id}"
        payload = {
            "question": request.question,
            "accessibility_profile": request.accessibility_profile.model_dump(mode="json"),
            "companion_profile": request.companion_profile.model_dump(mode="json"),
            "conversation_memory": [asdict(turn) for turn in self._memory.recall(memory_key)],
            "retrieval_context": context,
        }
        generated = self._validated(self._generator.generate(payload))
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
        return current.model_copy(update={
            "companionAnswer": answer,
            "prompts": prompts,
            "visualDrawer": drawer,
            "conversationContext": ConversationContext(scene_explanation=answer.answer),
        })

    def _retrieve(self, request: CompanionPipelineRequest, current: IntervalState, all_states: list[IntervalState]) -> dict[str, object]:
        query = self._embeddings.embed(request.question)
        vectors = {state.metadata.interval_id: self._embeddings.embed(_state_text(state)) for state in all_states}
        ranked = sorted(all_states, key=lambda state: cosine_similarity(query, vectors[state.metadata.interval_id]), reverse=True)
        prior = [state for state in all_states if state.metadata.start_time < current.metadata.start_time][-4:]
        related = _unique_states([current, *ranked], 6)
        entity_names = _unique_text(name for state in related for name in [*(card.name for card in state.characters), *state.semanticMemoryAfter.active_characters])
        relationships = _unique_text(value for state in related for value in [*(item.summary for item in state.relationships), *state.semanticMemoryAfter.relationships])
        conversations = _unique_text(state.conversationContext.scene_explanation for state in related)
        return {
            "current_scene": _state_evidence(current),
            "previous_events": [_state_evidence(state) for state in prior],
            "semantic_matches": [_state_evidence(state) for state in related],
            "entities": entity_names,
            "relationships": relationships,
            "conversations": conversations,
            "timeline": [_timeline_evidence(state) for state in _unique_states([*prior, current, *related], 10)],
            "conversation_memory": [asdict(turn) for turn in self._memory.recall(f"{request.movie_id}:{request.conversation_id}")],
        }

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
