"""Adapter contract for converting provider-specific output into fusion evidence."""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from schemas.fusion import PerceptionContribution

EvidenceT = TypeVar("EvidenceT")


class PerceptionEvidenceAdapter(ABC, Generic[EvidenceT]):
    """Future perception providers plug in by returning this common contribution shape."""

    @abstractmethod
    def to_contribution(self, evidence: EvidenceT) -> PerceptionContribution:
        """Normalize provider output without inferring a movie-character identity."""
