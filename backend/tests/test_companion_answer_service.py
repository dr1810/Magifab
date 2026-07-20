from pathlib import Path

from models.answer_generator import AnswerGenerator
from schemas.companion_pipeline import CompanionPipelineRequest
from schemas.interval_state import (
    CompanionAnswer, ConversationContext, IntervalCacheMetadata, IntervalMetadata,
    IntervalPrompts, IntervalSemanticMemory, IntervalStoryState, IntervalTimelineMemory,
    IntervalState, VisualDrawerState,
)
from schemas.profiles import AccessibilityProfile, CompanionProfile
from services.companion_answer_service import CompanionAnswerService
from services.conversation_memory import FileConversationMemory
from services.interval_state_store import IntervalStateRepository


class FakeSemanticIndex:
    def __init__(self):
        self.built = []

    def build(self, work_id, states):
        self.built.append((work_id, states))

    def retrieve(self, work_id, query, *, current_interval_id, allowed_kinds, entity_hints=(), limit=8):
        from services.semantic_retrieval import SemanticChunk
        return [SemanticChunk(
            id=f"{current_interval_id}:relationship:0", kind="relationship",
            text="Ellie confronts Rex about the map.", interval_id=current_interval_id,
            start_time=30, end_time=60, entities=("Rex", "Ellie"),
            relationships=("Rex and Ellie disagree about the map.",), source=f"interval:{current_interval_id}",
        )]

    def retrieve_with_scores(self, work_id, query, *, current_interval_id, allowed_kinds, entity_hints=(), mode="movie", current_position=None, current_text=None, intent=None, limit=8):
        from services.semantic_retrieval import RetrievedChunk
        return [RetrievedChunk(chunk, .91) for chunk in self.retrieve(work_id, query, current_interval_id=current_interval_id, allowed_kinds=allowed_kinds, entity_hints=entity_hints, limit=limit)]

    def expand_with_scores(self, work_id, query, *, current_interval_id, seed_chunks, allowed_kinds, entity_hints=(), mode="movie", current_position=None, current_text=None, intent=None, radius=1, limit=12):
        return seed_chunks


class FakeIntentRouter:
    def route(self, question):
        from services.intent_router import IntentRoute
        return IntentRoute("relationship", ("relationship",), "Relationship history and conflict between people.")


class FakeGenerator(AnswerGenerator):
    def __init__(self):
        self.payload = None

    def generate(self, payload):
        self.payload = payload
        return {
            "answer": "Rex and Ellie are arguing about the map.",
            "intent": "relationship",
            "visual_aid_type": "relationship_graph",
            "entities": ["Rex", "Ellie"],
            "relationships": ["Rex and Ellie disagree about the map."],
            "timeline_references": ["00:00–00:30", "00:30–01:00"],
            "suggested_follow_up_prompts": ["What happened before this?"],
        }

    def plan(self, payload):
        return {
            "intent": "relationship and cause",
            "evidence_requirements": ["current scene", "relationship history", "earlier events"],
            "search_queries": [payload["question"]],
            "timeline_scope": "earlier and current story events",
            "use_conversation_memory": True,
        }

    def generate_with_trace(self, payload):
        return self.generate(payload), '{"exact":"gemini request"}', '{"raw":"gemini response"}'


def _state(number: int, summary: str) -> IntervalState:
    start = number * 30.0
    return IntervalState(
        metadata=IntervalMetadata(interval_id=f"movie:interval:{number}", movie_id="movie", start_time=start, end_time=start + 30, interval_number=number, knowledge_revision=1),
        prompts=IntervalPrompts(), visualDrawer=VisualDrawerState(),
        storyState=IntervalStoryState(scene_summary=summary, current_interval_id=f"movie:interval:{number}"),
        conversationContext=ConversationContext(scene_explanation=summary),
        semanticMemoryBefore=IntervalSemanticMemory(),
        semanticMemoryAfter=IntervalSemanticMemory(active_characters=("Rex", "Ellie"), story_events=(summary,)),
        timelineMemory=IntervalTimelineMemory(current_event=summary),
        cacheMetadata=IntervalCacheMetadata(semantic_cache_key=f"key-{number}", knowledge_source="test", semantic_map_cached=True),
    )


def test_answer_service_retrieves_whole_work_and_remembers_followups(tmp_path: Path):
    states = IntervalStateRepository(tmp_path, 1)
    first, current = _state(0, "Rex finds the map."), _state(1, "Ellie confronts Rex about the map.")
    states.save(first)
    states.save(current)
    generator = FakeGenerator()
    memory = FileConversationMemory(tmp_path / "conversations")
    semantic_index = FakeSemanticIndex()
    service = CompanionAnswerService(states, generator, memory, semantic_index, FakeIntentRouter())
    service.preprocess_work("movie")
    request = CompanionPipelineRequest(movie_id="movie", timestamp_seconds=35, question="Why are they arguing?", conversation_id="session-1", accessibility_profile=AccessibilityProfile(), companion_profile=CompanionProfile())

    answered = service.answer(request, current)
    service.answer(request.model_copy(update={"question": "What happened before?"}), current)

    assert answered.companionAnswer == CompanionAnswer(**generator.generate(generator.payload))
    assert semantic_index.built[0][0] == "movie"
    assert generator.payload["intent_route"]["intent"] == "relationship"
    assert generator.payload["personal_memory"]["learning_preferences"]["reading_level"] == "adaptive"
    evidence = generator.payload["retrieval_context"]["evidence_chunks"]
    assert evidence == [{"id": "movie:interval:1:relationship:0", "kind": "relationship", "text": "Ellie confronts Rex about the map.", "source": "interval:movie:interval:1", "start_time": 30, "end_time": 60, "entities": ("Rex", "Ellie"), "relationships": ("Rex and Ellie disagree about the map.",)}]


def test_debug_trace_exposes_all_generation_stages(tmp_path: Path):
    states = IntervalStateRepository(tmp_path, 1)
    current = _state(0, "Ellie confronts Rex about the map.")
    states.save(current)
    service = CompanionAnswerService(states, FakeGenerator(), FileConversationMemory(tmp_path / "conversations"), FakeSemanticIndex(), FakeIntentRouter(), debug_enabled=True)
    service.preprocess_work("movie")
    request = CompanionPipelineRequest(movie_id="movie", timestamp_seconds=5, question="Why are they arguing?", accessibility_profile=AccessibilityProfile(), companion_profile=CompanionProfile())

    answered = service.answer(request, current)

    trace = answered.companionDebug
    assert trace is not None
    assert trace.user_question == "Why are they arguing?"
    assert trace.retrieval["top_chunks"][0]["similarity_score"] == .91
    assert trace.prompt == '{"exact":"gemini request"}'
    assert trace.gemini_response == '{"raw":"gemini response"}'
    assert trace.final_ui["companionAnswer"]["answer"] == "Rex and Ellie are arguing about the map."
    assert len(generator.payload["conversation_memory"]) == 1
    assert memory.recall("movie:session-1")[0].question == "Why are they arguing?"
