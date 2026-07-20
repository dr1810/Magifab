"""Pre-generation answerability gate for semantic retrieval evidence."""
from __future__ import annotations

from dataclasses import dataclass
import re

from services.semantic_retrieval import RetrievedChunk


@dataclass(frozen=True)
class RetrievalValidationResult:
    passed: bool
    reason: str
    anchor_terms: tuple[str, ...]


class RetrievalValidator:
    """Rejects weak or non-answer-bearing evidence before model generation."""

    def validate(self, question: str, intent: str, chunks: list[RetrievedChunk]) -> RetrievalValidationResult:
        anchors = _anchors(question)
        if not chunks:
            return RetrievalValidationResult(False, "No route-approved chunks were retrieved.", anchors)
        texts = " ".join(" ".join([item.chunk.text, *item.chunk.entities, *item.chunk.relationships]) for item in chunks).casefold()
        direct_anchors = [term for term in anchors if term.casefold() in texts]
        strongest = max(item.similarity_score for item in chunks)
        definition_kinds = {"glossary", "dialogue", "subtitle", "paragraph", "lore"}
        if intent == "definition" and not any(item.chunk.kind in definition_kinds for item in chunks):
            return RetrievalValidationResult(False, "Definition route returned no glossary, dialogue, subtitle, paragraph, or lore evidence.", anchors)
        if intent == "definition" and anchors and not direct_anchors:
            return RetrievalValidationResult(False, "Definition evidence does not contain the named term or linked entity from the question.", anchors)
        if anchors and not direct_anchors and strongest < .58:
            return RetrievalValidationResult(False, "Retrieved chunks do not contain a question anchor and are below the semantic answerability threshold.", anchors)
        if strongest < .42:
            return RetrievalValidationResult(False, "All retrieved chunks are below the semantic answerability threshold.", anchors)
        return RetrievalValidationResult(True, "Retrieved evidence passed anchor and semantic answerability checks.", anchors)


def _anchors(question: str) -> tuple[str, ...]:
    quoted = re.findall(r'["“]([^"”]{2,80})["”]', question)
    proper = re.findall(r"\b(?:[A-Z][\w-]+(?:\s+[A-Z][\w-]+){0,3})\b", question)
    terms = [*quoted, *proper]
    return tuple(dict.fromkeys(term.strip() for term in terms if term.strip()))
