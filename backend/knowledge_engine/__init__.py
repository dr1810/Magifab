"""Completion-gated, whole-work knowledge engine for MagiFab companions."""

from knowledge_engine.engine import KnowledgeEngine
from knowledge_engine.models import (
    BookIngestionRequest,
    MovieIngestionRequest,
    QuestionRequest,
)

__all__ = ["BookIngestionRequest", "KnowledgeEngine", "MovieIngestionRequest", "QuestionRequest"]
