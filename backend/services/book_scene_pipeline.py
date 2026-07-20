"""Page-context semantic pipeline for BookProvider intervals.

The reader never receives PDF text.  This service treats CleanPageDocument as
the only canonical input and emits the same immutable SceneState as Movie Mode.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import re

from schemas.accessibility_reasoning import CharacterCard, EmotionSummary, MemoryReminder, PromptBubbleSuggestion, RelationshipSummary
from schemas.clean_page_document import CleanPageDocument
from schemas.companion_pipeline import CompanionInterval, IntervalPreparationResponse
from schemas.interval_state import AccessibilityHints, ConversationContext, IntervalCacheMetadata, IntervalMetadata, IntervalPrompts, IntervalSemanticMemory, IntervalStoryState, IntervalTimelineMemory, VisualDrawerState
from services.page_document_normalizer import PageDocumentNormalizer
from services.interval_state_store import IntervalStateRepository


class BookScenePipeline:
    """Caches clean pages and derives spoiler-safe, page-local StoryState."""

    _proper_name = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")
    _emotion_words = {"afraid": "afraid", "angry": "angry", "sad": "sad", "worried": "worried", "happy": "happy", "relieved": "relieved", "nervous": "nervous"}
    _ignored_names = {"Chapter", "Page", "The", "A", "An", "He", "She", "They", "This", "That", "When", "What", "Why", "Where"}

    def __init__(self, normalizer: PageDocumentNormalizer | None = None, interval_states: IntervalStateRepository | None = None) -> None:
        self._normalizer = normalizer or PageDocumentNormalizer()
        self._interval_states = interval_states
        self._pages: dict[str, dict[int, CleanPageDocument]] = defaultdict(dict)
        self._states: dict[str, IntervalPreparationResponse] = {}

    def prepare(self, interval: CompanionInterval) -> IntervalPreparationResponse:
        documents = self._documents_from_interval(interval)
        for document in documents:
            self._pages[interval.contentId][document.page_number] = document
        page_start = int(interval.metadata.get("pageStart", documents[0].page_number))
        page_end = int(interval.metadata.get("pageEnd", documents[-1].page_number))
        cache_key = f"{interval.contentId}:{page_start}-{page_end}:{':'.join(document.source_hash for document in documents)}"
        if cache_key in self._states:
            return self._states[cache_key]
        context = [page for number, page in sorted(self._pages[interval.contentId].items()) if page_start - 2 <= number <= page_end]
        response = self._scene_state(interval, documents, context, page_start, page_end, cache_key)
        if self._interval_states is not None:
            self._interval_states.save(response)
        self._states[cache_key] = response
        return response

    def _documents_from_interval(self, interval: CompanionInterval) -> list[CleanPageDocument]:
        entries = interval.metadata.get("pageDocuments")
        if isinstance(entries, list):
            documents = [self._normalizer.normalize(interval.contentId, int(item["pageNumber"]), str(item.get("text", ""))) for item in entries if isinstance(item, dict) and isinstance(item.get("pageNumber"), int)]
            if documents:
                return documents
        page_start = int(interval.metadata.get("pageStart", 1))
        return [self._normalizer.normalize(interval.contentId, page_start, interval.text)]

    def _scene_state(self, interval: CompanionInterval, current: list[CleanPageDocument], context: list[CleanPageDocument], page_start: int, page_end: int, cache_key: str) -> IntervalPreparationResponse:
        current_text = " ".join(document.text for document in current)
        context_text = " ".join(document.text for document in context)
        characters = self._characters(current_text)
        names = [item.name for item in characters]
        emotion = self._emotion(current_text)
        objects = self._objects(current_text)
        memories = self._memory(context[:-len(current)] if len(context) > len(current) else [])
        summary = self._summary(page_start, page_end, names, emotion, objects)
        relationships = self._relationships(current_text, names)
        prompts = self._prompts(page_start, page_end, names, emotion, objects, bool(memories))
        interval_number = int(interval.start // 30)
        metadata = IntervalMetadata(interval_id=f"{interval.contentId}:interval:{interval_number}", movie_id=interval.contentId, start_time=interval.start, end_time=interval.end, interval_number=interval_number, knowledge_revision=1)
        return IntervalPreparationResponse(
            metadata=metadata,
            prompts=IntervalPrompts(prompt_bubbles=tuple(prompts), suggested_questions=tuple(item.question for item in prompts)),
            visualDrawer=VisualDrawerState(now=summary, story_now=(summary,), relationships=tuple(item.summary for item in relationships), timeline=(f"Pages {page_start}–{page_end}: {summary}",), emotion=emotion, objects=tuple(objects), memory=tuple(item.summary for item in memories)),
            storyState=IntervalStoryState(scene_summary=summary, current_goal=self._goal(names), current_interval_id=interval.id, timeline_position=f"Pages {page_start}–{page_end}", story_so_far=tuple(item.summary for item in memories), unresolved_threads=()),
            characters=tuple(characters), relationships=tuple(relationships), memory=tuple(memories),
            conversationContext=ConversationContext(scene_explanation=self._explanation(summary, names, emotion)),
            accessibilityHints=AccessibilityHints(emotions=(EmotionSummary(emotion_id=f"page-{page_start}-emotion", summary=f"The page feels {emotion}." if emotion else "The page's emotion is still becoming clear.", confidence=.65),) if emotion else ()),
            semanticMemoryBefore=IntervalSemanticMemory(active_characters=tuple(self._names(context_text))),
            semanticMemoryAfter=IntervalSemanticMemory(active_characters=tuple(names), relationships=tuple(item.summary for item in relationships), emotions=(emotion,) if emotion else (), important_objects=tuple(objects), story_events=(summary,)),
            timelineMemory=IntervalTimelineMemory(timeline_position=f"Pages {page_start}–{page_end}", previous_event=memories[-1].summary if memories else None, current_event=summary),
            cacheMetadata=IntervalCacheMetadata(semantic_cache_key=cache_key, knowledge_source="clean-page-semantic", semantic_map_cached=False, frame_hash=sha256(interval.image.encode("utf-8")).hexdigest()),
        )

    def _names(self, text: str) -> list[str]:
        values: list[str] = []
        for value in self._proper_name.findall(text):
            if value in self._ignored_names or value in values:
                continue
            values.append(value)
            if len(values) == 5:
                break
        return values

    def _characters(self, text: str) -> list[CharacterCard]:
        emotion = self._emotion(text)
        return [CharacterCard(character_id=f"character-{index}", name=name, reminder=f"A person involved in this page's events{f', currently {emotion}' if emotion else ''}.", confidence=.62) for index, name in enumerate(self._names(text), start=1)]

    def _emotion(self, text: str) -> str | None:
        lowered = text.casefold()
        return next((value for word, value in self._emotion_words.items() if word in lowered), None)

    def _objects(self, text: str) -> list[str]:
        candidates = re.findall(r"\b(key|letter|book|door|train|ring|map|ship|house|knife)\b", text, flags=re.I)
        return list(dict.fromkeys(value.casefold() for value in candidates))[:3]

    def _memory(self, pages: list[CleanPageDocument]) -> list[MemoryReminder]:
        return [MemoryReminder(summary=f"Earlier pages established the context leading into page {page.page_number}.", confidence=.6) for page in pages[-2:]]

    def _relationships(self, text: str, names: list[str]) -> list[RelationshipSummary]:
        if len(names) < 2:
            return []
        relation = "connected in the current scene"
        lowered = text.casefold()
        if "mother" in lowered or "father" in lowered or "son" in lowered or "daughter" in lowered:
            relation = "family relationship"
        return [RelationshipSummary(relationship_id="page-relationship-1", summary=f"{names[0]} and {names[1]}: {relation}.", confidence=.58)]

    @staticmethod
    def _summary(page_start: int, page_end: int, names: list[str], emotion: str | None, objects: list[str]) -> str:
        people = ", ".join(names[:2]) if names else "the people in the story"
        details = []
        if emotion:
            details.append(f"The mood is {emotion}")
        if objects:
            details.append(f"an important object is {objects[0]}")
        ending = ". ".join(details) if details else "The page introduces the next part of the situation"
        return f"On pages {page_start}–{page_end}, {people} are involved in the current story moment. {ending}."

    @staticmethod
    def _goal(names: list[str]) -> str | None:
        return f"Understand what {names[0]} needs in this moment." if names else "Understand the change happening in this moment."

    @staticmethod
    def _explanation(summary: str, names: list[str], emotion: str | None) -> str:
        focus = names[0] if names else "the people here"
        feeling = f" They may be feeling {emotion}." if emotion else ""
        return f"{summary} Focus on what {focus} is trying to do before reading ahead.{feeling}"

    @staticmethod
    def _prompts(page_start: int, page_end: int, names: list[str], emotion: str | None, objects: list[str], has_memory: bool) -> list[PromptBubbleSuggestion]:
        subject = names[0] if names else "this person"
        prompts = [PromptBubbleSuggestion(id=f"pages-{page_start}-who", kind="character", label=f"Who is {subject}?", question=f"Who is {subject} and why do they matter here?", priority=1, semantic_event=f"pages-{page_start}-{page_end}")]
        if emotion:
            prompts.append(PromptBubbleSuggestion(id=f"pages-{page_start}-emotion", kind="emotion", label="Why do they feel this way?", question=f"Why is {subject} feeling {emotion}?", priority=2))
        if has_memory:
            prompts.append(PromptBubbleSuggestion(id=f"pages-{page_start}-memory", kind="memory", label="What happened earlier?", question="What earlier event helps explain this page?", priority=3))
        if objects:
            prompts.append(PromptBubbleSuggestion(id=f"pages-{page_start}-object", kind="object", label=f"What does the {objects[0]} mean?", question=f"Why is the {objects[0]} important here?", priority=4))
        prompts.append(PromptBubbleSuggestion(id=f"pages-{page_start}-importance", kind="summary", label="Why is this important?", question="Why is this moment important to the story?", priority=5))
        return prompts[:5]
