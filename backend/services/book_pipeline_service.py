"""Durable, text-only book processing. It deliberately shares no movie/video code."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
from typing import Any
from uuid import uuid4

from schemas.book_pipeline import (
    BookChapterMetadata,
    BookChapterResponse,
    BookChaptersResponse,
    BookCharacter,
    BookProcessingStatusResponse,
    BookRelationship,
    CompanionQuestion,
    VisualMapEdge,
    VisualMapNode,
    VisualRelationshipMap,
)


@dataclass
class ExtractedPage:
    page_number: int
    text: str


@dataclass
class BookSegment:
    chapter_number: int
    chapter_title: str
    section_label: str
    page_start: int
    page_end: int
    text: str


class BookPipelineService:
    def __init__(self, root: Path, reasoner=None) -> None:
        self.root = root
        self.reasoner = reasoner
        self.root.mkdir(parents=True, exist_ok=True)
        self.index = self.root / "books.json"
        if not self.index.exists(): self.index.write_text("{}", encoding="utf-8")

    def upload(self, source: Path, filename: str, mime_type: str, title: str | None = None) -> dict[str, object]:
        digest = _hash(source)
        data = self._read()
        existing = next((item for item in data.values() if item["hash"] == digest), None)
        if existing: return {"book_id": existing["id"], "status": existing["status"], "reused_existing": True}
        book_id = str(uuid4())
        suffix = Path(filename).suffix.lower() or ".txt"
        target = self.root / "sources" / f"{book_id}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
        data[book_id] = {
            "id": book_id,
            "hash": digest,
            "title": title or Path(filename).stem,
            "filename": Path(filename).name,
            "mime_type": mime_type,
            "source": str(target),
            "status": "queued",
            "progress": "Waiting to process",
            "percentage": 0,
            "error": None,
            "chapter_count": 0,
        }
        self._write(data); return {"book_id": book_id, "status": "queued", "reused_existing": False}

    def start(self, book_id: str) -> bool:
        data = self._read(); book = self._book(data, book_id)
        if book["status"] == "complete": return False
        if book["status"] in {"extracting", "understanding", "reasoning"}: return False
        book.update(status="extracting", progress="Extracting text", percentage=5, error=None); self._write(data); return True

    def preprocess(self, book_id: str, profile: dict[str, object] | None = None) -> None:
        data = self._read(); book = self._book(data, book_id)
        try:
            pages = self._extract_pages(Path(book["source"]))
            pages = self._trim_to_narrative(pages)
            text = "\n\n".join(page.text for page in pages)
            if not text.strip():
                raise ValueError("No readable narrative text was found in this book after skipping front matter.")
            book.update(status="understanding", progress="Understanding chapters", percentage=35); self._write(data)
            chapters = self._chapters(pages)
            if not chapters:
                raise ValueError("No chapter or section chunks were generated from this book.")
            book.update(status="reasoning", progress="Building character relationships and accessibility explanations", percentage=70); self._write(data)
            artifacts = [self._artifact(segment, profile or {}) for segment in chapters]
            target = self.root / "artifacts" / f"{book_id}.json"; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(artifacts, ensure_ascii=False), encoding="utf-8")
            metadata = [
                {
                    "chapter_number": segment.chapter_number,
                    "chapter_title": segment.chapter_title,
                    "section_label": segment.section_label,
                    "page_start": segment.page_start,
                    "page_end": segment.page_end,
                }
                for segment in chapters
            ]
            book.update(
                status="complete",
                progress="Reading companion is ready",
                percentage=100,
                artifact=str(target),
                chapter_count=len(artifacts),
                chapters=metadata,
            )
            self._write(data)
        except Exception as error:
            current_percentage = int(book.get("percentage", 0)) if isinstance(book.get("percentage"), int) else 0
            book.update(status="failed", progress="Processing failed", percentage=max(current_percentage, 5), error=str(error)); self._write(data)

    def status(self, book_id: str) -> BookProcessingStatusResponse:
        data = self._read(); book = self._book(data, book_id)
        if book.get("status") == "complete" and (not isinstance(book.get("chapter_count"), int) or int(book.get("chapter_count", 0)) == 0):
            self._load_normalized_artifacts(book_id, data, book)
        count = int(book.get("chapter_count", 0)) if isinstance(book.get("chapter_count"), int) else 0
        return BookProcessingStatusResponse(status=book["status"], progress=book["progress"], percentage=book["percentage"], error=book.get("error"), chapter_count=count)

    def chapters(self, book_id: str) -> BookChaptersResponse:
        data = self._read(); book = self._book(data, book_id)
        if book.get("status") == "complete" and (not isinstance(book.get("chapters"), list) or not book.get("chapters")):
            self._load_normalized_artifacts(book_id, data, book)
        chapters = book.get("chapters", [])
        if not isinstance(chapters, list):
            chapters = []
        return BookChaptersResponse(book_id=book_id, chapters=[BookChapterMetadata.model_validate(item) for item in chapters])

    def chapter(self, book_id: str, chapter: int) -> BookChapterResponse:
        data = self._read(); book = self._book(data, book_id)
        if book["status"] != "complete": raise ValueError("Book artifacts are not ready.")
        artifacts = self._load_normalized_artifacts(book_id, data, book)
        if not artifacts: raise ValueError("No chapters were generated.")
        return BookChapterResponse.model_validate(artifacts[min(chapter - 1, len(artifacts) - 1)])

    def answer(self, book_id: str, chapter: int, question: str) -> tuple[str, int]:
        artifact = self.chapter(book_id, chapter)
        lower = question.lower()
        if "who" in lower and artifact.characters:
            return "; ".join(f"{entry.name}: {entry.description}" for entry in artifact.characters[:3]), artifact.chapter_number
        if "why" in lower and artifact.important_events:
            return " ".join(artifact.important_events[:3]), artifact.chapter_number
        if "relationship" in lower and artifact.relationships:
            return " ".join(f"{item.source} {item.relation} {item.target}." for item in artifact.relationships[:3]), artifact.chapter_number
        if "remember" in lower:
            return f"Remember: {artifact.memory_aid}", artifact.chapter_number
        return artifact.simple_explanation or artifact.chapter_summary, artifact.chapter_number

    def register_example(self, source: Path) -> str | None:
        if not source.is_file(): return None
        return str(self.upload(source, source.name, "application/pdf", "Dune")["book_id"])

    def example_id(self, title: str) -> str | None:
        for book in self._read().values():
            if str(book.get("title", "")).casefold() == title.casefold():
                return str(book["id"])
        return None

    def _extract_pages(self, source: Path) -> list[ExtractedPage]:
        if source.suffix.lower() == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(source))
            pages: list[ExtractedPage] = []
            for index, page in enumerate(reader.pages, start=1):
                pages.append(ExtractedPage(page_number=index, text=(page.extract_text() or "").strip()))
            return pages
        if source.suffix.lower() == ".epub":
            import zipfile
            with zipfile.ZipFile(source) as archive:
                text_blocks = [
                    re.sub(r"<[^>]+>", " ", archive.read(name).decode("utf-8", "ignore"))
                    for name in archive.namelist()
                    if name.lower().endswith((".xhtml", ".html", ".htm"))
                ]
            return [ExtractedPage(page_number=index + 1, text=" ".join(block.split())) for index, block in enumerate(text_blocks)]
        raw = source.read_text(encoding="utf-8", errors="replace")
        return [ExtractedPage(page_number=1, text=raw)]

    def _trim_to_narrative(self, pages: list[ExtractedPage]) -> list[ExtractedPage]:
        if not pages:
            return pages

        # If available, prefer an explicit Chapter One/Chapter 1 anchor.
        for index, page in enumerate(pages[:60]):
            if self._is_front_matter(page.text):
                continue
            if self._is_chapter_one_heading(page.text):
                return pages[index:]

        max_probe = min(len(pages), 30)
        start_index = 0
        for index in range(max_probe):
            text = pages[index].text
            if self._is_front_matter(text):
                start_index = index + 1
                continue
            if self._looks_like_chapter_heading(text):
                start_index = index
                break
            if self._narrative_score(text) >= 4 and not self._is_front_matter(text):
                start_index = index
                break
            start_index = index + 1
        if start_index >= len(pages):
            start_index = 0
        return pages[start_index:]

    @staticmethod
    def _is_front_matter(text: str) -> bool:
        lowered = text.casefold()
        front_matter_signals = [
            "all rights reserved",
            "copyright",
            "published by",
            "library of congress",
            "isbn",
            "table of contents",
            "contents",
            "acknowledg",
            "dedication",
            "foreword",
            "preface",
            "about the author",
            "printed in",
        ]
        return any(marker in lowered for marker in front_matter_signals)

    @staticmethod
    def _narrative_score(text: str) -> int:
        compact = " ".join(text.split())
        lowered = compact.casefold()
        score = 0
        if len(compact) > 800:
            score += 2
        if any(token in lowered for token in [" he ", " she ", " they ", " said ", " asked ", " looked "]):
            score += 2
        if compact.count("\"") >= 2:
            score += 1
        if compact.count(".") >= 8:
            score += 1
        if re.search(r"\bchapter\b|\bbook\b|\bpart\b", lowered):
            score += 2
        return score

    @staticmethod
    def _looks_like_chapter_heading(text: str) -> bool:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return False
        head = lines[0]
        return bool(re.match(r"(?i)^(chapter|book|part)\b[\w .'-]*$", head))

    @staticmethod
    def _is_chapter_one_heading(text: str) -> bool:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines[:10]:
            if re.match(r"(?i)^chapter\s+(one|1)\b[\w .'-]*$", line):
                return True
        return False

    def _chapters(self, pages: list[ExtractedPage]) -> list[BookSegment]:
        segments: list[BookSegment] = []
        buffer: list[str] = []
        chapter_number = 1
        start_page = pages[0].page_number
        end_page = pages[0].page_number
        active_title = "Opening"
        active_section = "narrative"

        def flush() -> None:
            nonlocal buffer, chapter_number, start_page, end_page, active_title, active_section
            text = "\n\n".join(chunk for chunk in buffer if chunk.strip()).strip()
            if text:
                segments.append(
                    BookSegment(
                        chapter_number=chapter_number,
                        chapter_title=active_title,
                        section_label=active_section,
                        page_start=start_page,
                        page_end=end_page,
                        text=text,
                    )
                )
                chapter_number += 1
            buffer = []

        for page in pages:
            page_text = page.text.strip()
            if not page_text:
                continue
            heading = _extract_heading(page_text)
            if heading and buffer:
                flush()
                start_page = page.page_number
            if heading:
                active_title = heading
                active_section = "chapter"
            end_page = page.page_number
            buffer.append(page_text)

        flush()
        if segments:
            return segments[:120]

        # Fallback segmentation by meaningful page ranges.
        fallback: list[BookSegment] = []
        pages_per_chunk = 8
        for offset in range(0, len(pages), pages_per_chunk):
            chunk_pages = pages[offset:offset + pages_per_chunk]
            text = "\n\n".join(page.text for page in chunk_pages).strip()
            if not text:
                continue
            number = len(fallback) + 1
            fallback.append(
                BookSegment(
                    chapter_number=number,
                    chapter_title=f"Section {number}",
                    section_label="page-range",
                    page_start=chunk_pages[0].page_number,
                    page_end=chunk_pages[-1].page_number,
                    text=text,
                )
            )
        return fallback[:120]

    def _artifact(self, segment: BookSegment, profile: dict[str, object]) -> dict[str, object]:
        if self.reasoner is not None:
            return self.reasoner.reason(
                chapter_number=segment.chapter_number,
                chapter_title=segment.chapter_title,
                section_label=segment.section_label,
                page_start=segment.page_start,
                page_end=segment.page_end,
                text=segment.text,
                profile=profile,
            ).model_dump(mode="json")

        clean = " ".join(segment.text.split())
        names = list(dict.fromkeys(re.findall(r"\b[A-Z][a-z]{2,}\b", clean)))[:12]
        summary = clean[:1600] or "This section has very little extractable text."
        events = _top_sentences(clean, 3)
        difficult = [item for item in re.findall(r"\b[A-Z][A-Za-z'-]{5,}\b", clean) if item not in names][:4]
        style = profile.get("preferred_explanation_style", "supportive")
        difficulties = profile.get("difficulties", []) if isinstance(profile.get("difficulties"), list) else []
        memory_needs = profile.get("memory_requirements", []) if isinstance(profile.get("memory_requirements"), list) else []
        visual_needs = profile.get("visual_assistance_needs", []) if isinstance(profile.get("visual_assistance_needs"), list) else []
        characters = [BookCharacter(name=name, description=f"Appears in {segment.chapter_title}.") for name in names]
        relationships = [BookRelationship(source=names[0], relation="interacts with", target=names[1])] if len(names) > 1 else []
        nodes = [VisualMapNode(id=name.lower().replace(" ", "-"), label=name) for name in names[:8]]
        edges = [
            VisualMapEdge(
                source=relationships[0].source.lower().replace(" ", "-"),
                target=relationships[0].target.lower().replace(" ", "-"),
                label=relationships[0].relation,
            )
        ] if relationships else []
        questions = [
            CompanionQuestion(label="What is happening?", question="What is happening in this chapter?"),
            CompanionQuestion(label="Who is this?", question="Who is this person and why are they important now?"),
            CompanionQuestion(label="Why did this happen?", question="Why did this event happen in this chapter?"),
        ]
        return BookChapterResponse(
            chapter_number=segment.chapter_number,
            chapter_title=segment.chapter_title[:180],
            section_label=segment.section_label,
            page_start=segment.page_start,
            page_end=segment.page_end,
            chapter_summary=summary,
            simple_explanation=_simple_explanation(summary, style, difficulties, memory_needs, visual_needs),
            characters=characters,
            relationships=relationships,
            important_events=events,
            difficult_concepts=difficult,
            memory_aid=events[0] if events else summary[:220],
            visual_relationship_map=VisualRelationshipMap(nodes=nodes, edges=edges),
            companion_questions=questions,
            confidence=0.62,
        ).model_dump(mode="json")

    def _load_normalized_artifacts(self, book_id: str, data: dict[str, dict[str, object]], book: dict[str, object]) -> list[dict[str, object]]:
        artifact_path = Path(str(book.get("artifact", "")))
        if not artifact_path.is_file():
            return []

        raw = json.loads(artifact_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []

        normalized: list[dict[str, object]] = []
        changed = False
        for index, item in enumerate(raw, start=1):
            try:
                if isinstance(item, dict):
                    normalized_item = BookChapterResponse.model_validate(item).model_dump(mode="json")
                else:
                    normalized_item = self._upgrade_legacy_artifact({"summary": str(item)}, index)
                normalized.append(normalized_item)
            except Exception:
                changed = True
                if isinstance(item, dict):
                    normalized.append(self._upgrade_legacy_artifact(item, index))
                else:
                    normalized.append(self._upgrade_legacy_artifact({"summary": str(item)}, index))

        metadata = [
            {
                "chapter_number": int(item["chapter_number"]),
                "chapter_title": str(item["chapter_title"]),
                "section_label": str(item.get("section_label", "chapter")),
                "page_start": int(item["page_start"]),
                "page_end": int(item["page_end"]),
            }
            for item in normalized
        ]

        existing_count = int(book.get("chapter_count", 0)) if isinstance(book.get("chapter_count"), int) else 0
        existing_chapters = book.get("chapters")
        if changed or existing_count != len(normalized) or not isinstance(existing_chapters, list) or len(existing_chapters) != len(metadata):
            artifact_path.write_text(json.dumps(normalized, ensure_ascii=False), encoding="utf-8")
            book.update(chapter_count=len(normalized), chapters=metadata)
            data[book_id] = book
            self._write(data)

        return normalized

    def _upgrade_legacy_artifact(self, legacy: dict[str, Any], fallback_number: int) -> dict[str, object]:
        chapter_number = _coerce_positive_int(legacy.get("chapter"), fallback_number)
        chapter_title = str(legacy.get("title") or f"Chapter {chapter_number}")
        chapter_summary = str(legacy.get("summary") or "")

        raw_characters = legacy.get("characters")
        characters: list[BookCharacter] = []
        if isinstance(raw_characters, list):
            for item in raw_characters:
                if isinstance(item, dict):
                    name = str(item.get("name") or "Unknown")
                    description = str(item.get("description") or "No description available.")
                else:
                    name = str(item)
                    description = "Mentioned in this chapter."
                characters.append(BookCharacter(name=name[:120], description=description[:500]))

        raw_relationships = legacy.get("relationships")
        relationships: list[BookRelationship] = []
        if isinstance(raw_relationships, list):
            for entry in raw_relationships:
                if isinstance(entry, dict):
                    source = str(entry.get("source") or entry.get("from") or "Unknown")
                    relation = str(entry.get("relation") or entry.get("relationship") or "related to")
                    target = str(entry.get("target") or entry.get("to") or "Unknown")
                    relationships.append(BookRelationship(source=source[:120], relation=relation[:180], target=target[:120]))
                elif isinstance(entry, str) and entry.strip():
                    relationships.append(BookRelationship(source="Context", relation=entry.strip()[:180], target="Context"))

        old_map = legacy.get("visualRelationshipMap")
        map_nodes: list[VisualMapNode] = []
        map_edges: list[VisualMapEdge] = []
        if isinstance(old_map, dict):
            nodes = old_map.get("nodes")
            if isinstance(nodes, list):
                for node in nodes:
                    if isinstance(node, dict):
                        label = str(node.get("label") or node.get("name") or node.get("id") or "Node")
                        node_id = str(node.get("id") or label.casefold().replace(" ", "-"))
                    else:
                        label = str(node)
                        node_id = label.casefold().replace(" ", "-")
                    map_nodes.append(VisualMapNode(id=node_id[:120], label=label[:120]))

            edges = old_map.get("edges")
            if isinstance(edges, list):
                for edge in edges:
                    if isinstance(edge, dict):
                        source = str(edge.get("source") or edge.get("from") or "Context")
                        target = str(edge.get("target") or edge.get("to") or "Context")
                        label = str(edge.get("label") or edge.get("relation") or edge.get("relationship") or "related to")
                    elif isinstance(edge, list) and len(edge) >= 2:
                        source = str(edge[0])
                        target = str(edge[1])
                        label = "related to"
                    else:
                        continue
                    map_edges.append(VisualMapEdge(source=source[:120], target=target[:120], label=label[:180]))

        if not map_nodes:
            for character in characters[:12]:
                map_nodes.append(VisualMapNode(id=character.name.casefold().replace(" ", "-")[:120], label=character.name[:120]))
        if not map_edges and relationships:
            for rel in relationships[:12]:
                map_edges.append(VisualMapEdge(source=rel.source, target=rel.target, label=rel.relation))

        timeline = legacy.get("timeline") if isinstance(legacy.get("timeline"), list) else []
        important_events = [str(item) for item in timeline if str(item).strip()][:5]
        if not important_events:
            important_events = _top_sentences(chapter_summary, 3)

        glossary = legacy.get("glossary") if isinstance(legacy.get("glossary"), list) else []
        difficult_concepts: list[str] = []
        for item in glossary:
            if isinstance(item, dict):
                term = str(item.get("term") or "").strip()
                if term:
                    difficult_concepts.append(term)
        difficult_concepts = difficult_concepts[:6]

        memory_aids = legacy.get("memoryAids") if isinstance(legacy.get("memoryAids"), list) else []
        memory_aid = str(memory_aids[0]) if memory_aids else chapter_summary[:220]

        return BookChapterResponse(
            chapter_number=chapter_number,
            chapter_title=chapter_title[:180],
            section_label="chapter",
            page_start=max(1, chapter_number),
            page_end=max(1, chapter_number),
            chapter_summary=chapter_summary,
            simple_explanation=chapter_summary,
            characters=characters,
            relationships=relationships,
            important_events=important_events,
            difficult_concepts=difficult_concepts,
            memory_aid=memory_aid,
            visual_relationship_map=VisualRelationshipMap(nodes=map_nodes, edges=map_edges),
            companion_questions=[
                CompanionQuestion(label="What is happening?", question="What is happening in this chapter?"),
                CompanionQuestion(label="Who matters here?", question="Who are the important people in this chapter?"),
                CompanionQuestion(label="What should I remember?", question="What is the key thing to remember from this chapter?"),
            ],
            confidence=0.35,
        ).model_dump(mode="json")

    def _read(self) -> dict[str, dict[str, object]]: return json.loads(self.index.read_text(encoding="utf-8"))
    def _write(self, data: dict[str, object]) -> None: self.index.write_text(json.dumps(data), encoding="utf-8")
    @staticmethod
    def _book(data: dict[str, dict[str, object]], book_id: str) -> dict[str, object]:
        if book_id not in data: raise KeyError("book_not_found")
        return data[book_id]


def _hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()


def _extract_heading(text: str) -> str | None:
    for line in text.splitlines()[:8]:
        candidate = line.strip()
        if not candidate:
            continue
        if re.match(r"(?i)^(chapter|book|part)\b[\w .'-]*$", candidate):
            return candidate.title()
    return None


def _top_sentences(text: str, limit: int) -> list[str]:
    sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", text) if segment.strip()]
    return sentences[:limit]


def _simple_explanation(summary: str, style: object, difficulties: list[object], memory_needs: list[object], visual_needs: list[object]) -> str:
    parts = [summary[:500]]
    if style:
        parts.append(f"Style: {style}.")
    if difficulties:
        parts.append("Support focus: " + ", ".join(str(item) for item in difficulties[:4]) + ".")
    if memory_needs:
        parts.append("Memory aid focus: " + ", ".join(str(item) for item in memory_needs[:3]) + ".")
    if visual_needs:
        parts.append("Visual support focus: " + ", ".join(str(item) for item in visual_needs[:3]) + ".")
    return " ".join(parts)


def _coerce_positive_int(value: object, fallback: int) -> int:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        if parsed > 0:
            return parsed
    return max(1, fallback)
