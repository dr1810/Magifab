"""Semantic intent classifier that chooses an evidence policy before generation."""
from __future__ import annotations

from dataclasses import dataclass

from services.semantic_retrieval import SemanticEmbeddingProvider


@dataclass(frozen=True)
class IntentRoute:
    intent: str
    evidence_kinds: tuple[str, ...]
    retrieval_instruction: str


class SemanticIntentRouter:
    """Routes by semantic similarity to intent descriptions, never keyword rules."""

    def __init__(self, embeddings: SemanticEmbeddingProvider) -> None:
        self._embeddings = embeddings
        self._routes = _routes()
        self._vectors: tuple[tuple[float, ...], ...] | None = None

    def route(self, question: str) -> IntentRoute:
        if self._vectors is None:
            self._vectors = tuple(self._embeddings.embed_documents([route.retrieval_instruction for route in self._routes]))
        query = self._embeddings.embed_query(question)
        selected = max(zip(self._routes, self._vectors, strict=True), key=lambda item: _cosine(query, item[1]))
        return selected[0]


def _routes() -> tuple[IntentRoute, ...]:
    return (
        IntentRoute("character", ("character", "relationship", "dialogue", "event"), "Identity, role, goals, motivations, and who a person is in the story."),
        IntentRoute("relationship", ("relationship", "character", "dialogue", "event"), "The connection, conflict, family, alliance, or history between people."),
        IntentRoute("emotion", ("emotion", "dialogue", "event", "relationship"), "A character's feelings, emotional change, and evidence for why they feel that way."),
        IntentRoute("cause_effect", ("event", "timeline", "relationship", "emotion"), "Why something happened, its cause, consequence, and narrative effect."),
        IntentRoute("timeline", ("timeline", "event", "scene", "paragraph"), "What happened earlier, when events occurred, or the sequence of story events."),
        IntentRoute("conversation", ("dialogue", "quote", "relationship", "event"), "What people said, meant, wanted, or discussed in a conversation."),
        IntentRoute("memory", ("event", "timeline", "character", "relationship", "quote"), "A callback, earlier story memory, or information the reader should recall."),
        IntentRoute("object", ("object", "event", "scene", "paragraph"), "An important object, who owns it, where it appeared, and why it matters."),
        IntentRoute("location", ("location", "scene", "paragraph", "lore"), "A setting, place, where someone is, or the meaning of a location."),
        IntentRoute("definition", ("glossary", "subtitle", "dialogue", "ocr", "paragraph", "lore"), "The meaning, name, term, phrase, word, title, or definition used in the source."),
        IntentRoute("world_building", ("lore", "location", "organization", "paragraph", "glossary"), "How the fictional world, society, culture, rules, or setting works."),
        IntentRoute("lore", ("lore", "organization", "glossary", "paragraph", "timeline"), "Background knowledge, history, mythology, institutions, or established story facts."),
        IntentRoute("summary", ("chapter", "scene", "event", "timeline", "paragraph"), "A concise summary of a scene, page, chapter, or section."),
        IntentRoute("prediction", ("foreshadowing", "event", "relationship", "scene"), "A grounded prediction based on clues, setup, and unresolved story threads."),
        IntentRoute("comparison", ("character", "relationship", "event", "paragraph"), "Similarities, differences, changes, or comparison between people, events, or concepts."),
        IntentRoute("visual_explanation", ("scene", "object", "emotion", "location"), "What is visually happening, body language, appearance, action, and visual context."),
        IntentRoute("movie_specific", ("scene", "dialogue", "object", "timeline"), "A movie moment, shot, on-screen action, dialogue, or playback-specific question."),
        IntentRoute("book_specific", ("chapter", "paragraph", "glossary", "lore", "timeline"), "A book paragraph, page, chapter, sentence, prose passage, or reading-specific question."),
    )


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))
