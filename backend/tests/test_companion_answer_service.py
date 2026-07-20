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
    service = CompanionAnswerService(states, generator, memory)
    request = CompanionPipelineRequest(movie_id="movie", timestamp_seconds=35, question="Why are they arguing?", conversation_id="session-1", accessibility_profile=AccessibilityProfile(), companion_profile=CompanionProfile())

    answered = service.answer(request, current)
    service.answer(request.model_copy(update={"question": "What happened before?"}), current)

    assert answered.companionAnswer == CompanionAnswer(**generator.generate(generator.payload))
    assert generator.payload["retrieval_context"]["current_scene"]["interval_id"] == "movie:interval:1"
    assert generator.payload["retrieval_context"]["previous_events"][0]["interval_id"] == "movie:interval:0"
    assert generator.payload["reasoning_plan"]["intent"] == "relationship and cause"
    assert generator.payload["personal_memory"]["learning_preferences"]["reading_level"] == "adaptive"
    entity_memory = generator.payload["retrieval_context"]["entity_memories"]
    assert {item["entity"] for item in entity_memory} == {"Rex", "Ellie"}
    assert generator.payload["retrieval_context"]["multi_hop_evidence"]
    assert len(generator.payload["conversation_memory"]) == 1
    assert memory.recall("movie:session-1")[0].question == "Why are they arguing?"
