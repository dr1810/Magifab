"""Turn PDF text-layer output into a canonical, page-scoped document."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import re

from schemas.clean_page_document import CleanPageDocument


class PageDocumentNormalizer:
    """Removes presentation noise without changing the author-facing page text."""

    _watermark = re.compile(r"\b(converted to pdf|created with|www\.[\w.-]+\.(com|org)|confidential|draft)\b", re.I)
    _page_number = re.compile(r"^\s*(page\s+)?\d{1,4}\s*$", re.I)
    _space = re.compile(r"[ \t]+")
    _line_break = re.compile(r"(?<=[a-z,;:])\n(?=[a-z])")

    def __init__(self) -> None:
        self._repeated_lines: dict[str, Counter[str]] = {}

    def normalize(self, content_id: str, page_number: int, raw_text: str) -> CleanPageDocument:
        lines = [self._clean_line(line) for line in raw_text.replace("\r", "").split("\n")]
        lines = [line for line in lines if line and not self._is_noise(line)]
        repeated = self._repeated_lines.setdefault(content_id, Counter())
        repeated.update(set(lines))
        lines = [line for line in lines if repeated[line] < 3]
        joined = "\n".join(lines)
        joined = self._line_break.sub(" ", joined)
        paragraphs = tuple(self._dedupe(self._paragraphs(joined)))
        chapter_title = self._chapter_title(paragraphs)
        quotations = tuple(part for part in paragraphs if self._contains_dialogue(part))
        source_hash = sha256("\n".join(paragraphs).encode("utf-8")).hexdigest()
        return CleanPageDocument(content_id=content_id, page_number=page_number, chapter_title=chapter_title, paragraphs=paragraphs, quotations=quotations, source_hash=source_hash)

    def _is_noise(self, line: str) -> bool:
        return bool(self._page_number.match(line) or self._watermark.search(line))

    def _clean_line(self, line: str) -> str:
        return self._space.sub(" ", line).strip(" \t•")

    @staticmethod
    def _paragraphs(text: str) -> list[str]:
        candidates = [re.sub(r"\s+", " ", value).strip() for value in re.split(r"\n{2,}", text)]
        return [value for value in candidates if len(value) > 1]

    @staticmethod
    def _dedupe(values: tuple[str, ...] | list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            key = value.casefold()
            if key and key not in seen:
                seen.add(key)
                result.append(value)
        return result

    @staticmethod
    def _contains_dialogue(value: str) -> bool:
        return '"' in value or '“' in value or '”' in value

    @staticmethod
    def _chapter_title(paragraphs: tuple[str, ...]) -> str | None:
        if not paragraphs:
            return None
        first = paragraphs[0]
        if len(first.split()) <= 12 and not first.endswith((".", "!", "?")):
            return first
        return None
