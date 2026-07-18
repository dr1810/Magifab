"""Replaceable contract for turning verified facts into accessible language."""
from abc import ABC, abstractmethod

from schemas.personalization import GPTPersonalizationRequest


class LanguagePersonalizer(ABC):
    """Language-only boundary. Implementations cannot receive image or perception input."""

    @abstractmethod
    def personalize(self, request: GPTPersonalizationRequest) -> tuple[str, str]:
        """Return accessible text and the model/provider identifier used."""
