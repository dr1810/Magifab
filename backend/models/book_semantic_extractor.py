"""Extraction boundary for grounded full-book preprocessing."""
from abc import ABC, abstractmethod


class BookSemanticExtractor(ABC):
    @abstractmethod
    def extract(self, *, paragraph: str, page_number: int, chapter_title: str | None) -> dict[str, object]:
        """Return source-bound facts only; never answer a user question."""
