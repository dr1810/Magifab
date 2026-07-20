"""Regression coverage for per-question evidence retrieval.

These fixtures mirror the companion's Sprite Fright and Dune examples.  The
generator deliberately derives its answer from supplied evidence, so a stale
retrieval result cannot satisfy two different questions by accident.
"""
from pathlib import Path

from models.answer_generator import AnswerGenerator
from schemas.companion_pipeline import CompanionPipelineRequest
from schemas.interval_state import (
    ConversationContext, IntervalCacheMetadata, IntervalMetadata, IntervalPrompts,
    IntervalSemanticMemory, IntervalStoryState, IntervalTimelineMemory,
    IntervalState, SourceContext, VisualDrawerState,
)
from schemas.profiles import AccessibilityProfile, CompanionProfile
from services.companion_answer_service import CompanionAnswerService
from services.conversation_memory import FileConversationMemory
from services.intent_router import IntentRoute
from services.interval_state_store import IntervalStateRepository
from services.semantic_retrieval import RetrievedChunk, SemanticChunk


class FixtureIntentRouter:
    def route(self, question):
        normalized = question.casefold()
        if "latin name" in normalized or "gom jabbar" in normalized:
            return IntentRoute("definition", ("glossary", "subtitle", "dialogue", "paragraph"), "Retrieve the named term from dialogue, subtitles, or glossary evidence.")
        if "annoyed" in normalized:
            return IntentRoute("emotion", ("relationship", "event", "dialogue"), "Retrieve the emotional cause and relationship history.")
        if "sprites" in normalized:
            return IntentRoute("character", ("character", "event", "dialogue"), "Retrieve the character's goals and actions.")
        return IntentRoute("character", ("character", "paragraph", "lore"), "Retrieve the named person's identity and current story facts.")


class FixtureSemanticIndex:
    def __init__(self):
        self.calls = []

    def build(self, work_id, states):
        return None

    def retrieve_with_scores(self, work_id, query, *, current_interval_id, allowed_kinds, entity_hints=(), mode="movie", current_position=None, current_text=None, intent=None, limit=8):
        self.calls.append({"query": query, "mode": mode, "current_position": current_position, "current_text": current_text, "intent": intent})
        text, kind, entities = _fixture_evidence(query)
        chunk = SemanticChunk(f"{current_interval_id}:{kind}", kind, text, current_interval_id, float(current_position or 0), None, entities, (), f"interval:{current_interval_id}")
        return [RetrievedChunk(chunk, .95)]

    def expand_with_scores(self, *args, **kwargs):
        raise AssertionError("Fixture evidence should pass validation without retry")


class EvidenceGenerator(AnswerGenerator):
    def __init__(self):
        self.payloads = []

    def generate(self, payload):
        self.payloads.append(payload)
        evidence = payload["retrieval_context"]["evidence_chunks"][0]["text"]
        answer = _answer_from_evidence(evidence)
        return {
            "answer": answer,
            "intent": payload["intent_route"]["intent"],
            "visual_aid_type": "story_summary",
            "entities": [],
            "relationships": [],
            "timeline_references": [],
            "suggested_follow_up_prompts": [],
        }

    def plan(self, payload):
        raise AssertionError("Answering must use the dedicated retrieval route, not a generic plan.")


def _fixture_evidence(query):
    normalized = query.casefold()
    if "latin name" in normalized:
        return "Ellie calls the snail Cornu aspersum.", "subtitle", ("Ellie", "Snail")
    if "annoyed" in normalized:
        return "Rex and Victoria are annoyed because Ellie keeps stopping to study wildlife.", "relationship", ("Rex", "Victoria", "Ellie")
    if "sprites" in normalized:
        return "The sprites want to protect the forest from intruders.", "character", ("Sprites",)
    if "gom jabbar" in normalized:
        return "Gom Jabbar: a needle used by the Reverend Mother in the test.", "glossary", ("Gom Jabbar", "Reverend Mother")
    if "old woman" in normalized:
        return "The old woman is Reverend Mother Gaius Helen Mohiam.", "character", ("Reverend Mother Gaius Helen Mohiam",)
    if "planet" in normalized:
        return "Paul is going to the planet Arrakis.", "paragraph", ("Paul", "Arrakis")
    raise AssertionError(f"Unexpected test question: {query}")


def _answer_from_evidence(evidence):
    if "Cornu aspersum" in evidence:
        return "Ellie says Cornu aspersum."
    if "keeps stopping" in evidence:
        return "Rex and Victoria are annoyed because Ellie keeps stopping to study wildlife."
    if "protect the forest" in evidence:
        return "The sprites want to protect the forest."
    if "needle used by the Reverend Mother" in evidence:
        return "A Gom Jabbar is a needle used by the Reverend Mother."
    if "Gaius Helen Mohiam" in evidence:
        return "The old woman is Reverend Mother Gaius Helen Mohiam."
    if "Arrakis" in evidence:
        return "Paul is going to Arrakis."
    raise AssertionError(f"Generator received unrelated evidence: {evidence}")


def _state(work_id, number, *, mode, position, visible_text):
    return IntervalState(
        metadata=IntervalMetadata(interval_id=f"{work_id}:interval:{number}", movie_id=work_id, start_time=float(position), end_time=float(position) + 1, interval_number=number, knowledge_revision=1),
        prompts=IntervalPrompts(), visualDrawer=VisualDrawerState(),
        storyState=IntervalStoryState(scene_summary="Prepared narrative interval.", current_interval_id=f"{work_id}:interval:{number}"),
        conversationContext=ConversationContext(scene_explanation="Prepared narrative interval."),
        semanticMemoryBefore=IntervalSemanticMemory(), semanticMemoryAfter=IntervalSemanticMemory(),
        timelineMemory=IntervalTimelineMemory(current_event="Prepared narrative interval."),
        cacheMetadata=IntervalCacheMetadata(semantic_cache_key=f"{work_id}-{number}", knowledge_source="test", semantic_map_cached=True),
        sourceContext=SourceContext(mode=mode, subtitle=visible_text if mode == "movie" else None, visible_text=visible_text, page_start=int(position) if mode == "book" else None, page_end=int(position) if mode == "book" else None),
    )


def _answer(service, state, question):
    request = CompanionPipelineRequest(movie_id=state.metadata.movie_id, timestamp_seconds=state.metadata.start_time, question=question, conversation_id="fresh-retrieval", accessibility_profile=AccessibilityProfile(), companion_profile=CompanionProfile())
    return service.answer(request, state).companionAnswer.answer


def test_movie_questions_use_fresh_question_specific_evidence(tmp_path: Path):
    states = IntervalStateRepository(tmp_path, 1)
    current = _state("sprite-fright", 0, mode="movie", position=22, visible_text="Aw, you cute little cornu aspersum.")
    states.save(current)
    index, generator = FixtureSemanticIndex(), EvidenceGenerator()
    service = CompanionAnswerService(states, generator, FileConversationMemory(tmp_path / "memory"), index, FixtureIntentRouter())
    service.preprocess_work("sprite-fright")

    answers = [
        _answer(service, current, "What is the Latin name Ellie says?"),
        _answer(service, current, "Why are Rex and Victoria annoyed?"),
        _answer(service, current, "What do the sprites want?"),
    ]

    assert "Cornu aspersum" in answers[0]
    assert "Ellie keeps stopping to study wildlife" in answers[1]
    assert "protect the forest" in answers[2].casefold()
    assert len(set(answers)) == len(answers)
    assert len({call["query"] for call in index.calls}) == 3
    assert all(call["mode"] == "movie" and call["current_position"] == 22 for call in index.calls)


def test_book_questions_use_fresh_book_wide_evidence(tmp_path: Path):
    states = IntervalStateRepository(tmp_path, 1)
    current = _state("dune", 7, mode="book", position=7, visible_text="Paul prepares to leave for Arrakis.")
    states.save(current)
    index, generator = FixtureSemanticIndex(), EvidenceGenerator()
    service = CompanionAnswerService(states, generator, FileConversationMemory(tmp_path / "memory"), index, FixtureIntentRouter())
    service.preprocess_work("dune")

    answers = [
        _answer(service, current, "What is a Gom Jabbar?"),
        _answer(service, current, "Who is the old woman?"),
        _answer(service, current, "What planet is Paul going to?"),
    ]

    assert "needle used by the Reverend Mother" in answers[0]
    assert "Reverend Mother Gaius Helen Mohiam" in answers[1]
    assert "Arrakis" in answers[2]
    assert len(set(answers)) == len(answers)
    assert len({call["query"] for call in index.calls}) == 3
    assert all(call["mode"] == "book" and call["current_position"] == 7 for call in index.calls)
