"""Provider boundary for structured, grounded companion answers."""
from abc import ABC, abstractmethod


class AnswerGenerator(ABC):
    @abstractmethod
    def generate(self, payload: dict[str, object]) -> dict[str, object]:
        """Generate a validated answer using only the supplied retrieval context."""
