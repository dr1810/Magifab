"""Whole-book semantic preprocessing and persistent graph construction."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import re

from models.book_semantic_extractor import BookSemanticExtractor
from schemas.book_knowledge import BookIngestionRequest, BookKnowledgeIngestionResult
from services.page_document_normalizer import PageDocumentNormalizer
from services.semantic_retrieval import SemanticChunk, SemanticRetrievalIndex


class BookKnowledgePreprocessor:
    def __init__(self, extractor: BookSemanticExtractor, index: SemanticRetrievalIndex, graph_root: Path, normalizer: PageDocumentNormalizer | None = None) -> None:
        self._extractor = extractor
        self._index = index
        self._graph_root = graph_root
        self._normalizer = normalizer or PageDocumentNormalizer()

    def preprocess(self, request: BookIngestionRequest) -> BookKnowledgeIngestionResult:
        documents = [self._normalizer.normalize(request.book_id, page.page_number, page.text) for page in request.pages]
        chapters = _chapters(documents)
        chunks: list[SemanticChunk] = []
        graph = {"book_id": request.book_id, "chapters": chapters, "entities": {}, "relationships": [], "concepts": {}}
        chapter_summaries: dict[str, list[str]] = {}
        for document in documents:
            chapter = _chapter_for(document.page_number, chapters)
            for index, paragraph in enumerate(document.paragraphs):
                analysis = self._extractor.extract(paragraph=paragraph, page_number=document.page_number, chapter_title=chapter)
                source = f"page:{document.page_number}:paragraph:{index}"
                base = _base(request.book_id, document.page_number, source, _names(analysis, "entities"), _relationships(analysis))
                chunks.append(SemanticChunk(id=f"{source}:paragraph", kind="paragraph", text=paragraph[:900], **base))
                _append(chunks, "scene", _text(analysis, "summary"), f"{source}:summary", base)
                _append_many(chunks, "event", _texts(analysis, "events"), source, base)
                _append_many(chunks, "quote", [quote for quote in _texts(analysis, "quotes") if quote in paragraph], source, base)
                for item in _items(analysis, "definitions"):
                    _append(chunks, "glossary", f"{item['term']}: {item['definition']}", f"{source}:definition:{item['term']}", base)
                for item in _items(analysis, "concepts"):
                    _append(chunks, "lore", f"{item['name']}: {item['description']}", f"{source}:concept:{item['name']}", base)
                    graph["concepts"].setdefault(item["name"].casefold(), {"name": item["name"], "description": item["description"], "sources": []})["sources"].append(source)
                for item in _items(analysis, "entities"):
                    _append(chunks, item["kind"].casefold() if item["kind"].casefold() in {"character", "object", "location", "organization"} else "lore", f"{item['name']}: {item['description']}", f"{source}:entity:{item['name']}", base)
                    graph["entities"].setdefault(item["name"].casefold(), {"name": item["name"], "kind": item["kind"], "description": item["description"], "sources": []})["sources"].append(source)
                for relation in _relationships(analysis):
                    text = f"{relation['subject']} {relation['predicate']} {relation['object']}"
                    _append(chunks, "relationship", text, f"{source}:relationship:{len(graph['relationships'])}", base)
                    graph["relationships"].append({**relation, "source": source})
                summary = _text(analysis, "summary")
                if summary:
                    chapter_summaries.setdefault(chapter or "Opening", []).append(summary)
        for chapter, summaries in chapter_summaries.items():
            page = next(item["start_page"] for item in chapters if item["title"] == chapter) if chapter in {item["title"] for item in chapters} else 1
            base = _base(request.book_id, page, f"chapter:{chapter}", (), ())
            _append(chunks, "chapter", " ".join(summaries)[:900], f"chapter:{chapter}:summary", base)
        self._index.build(request.book_id, [], tuple(chunks))
        self._save_graph(request.book_id, graph)
        return BookKnowledgeIngestionResult(book_id=request.book_id, pages_processed=len(documents), chapters_detected=len(chapters), semantic_chunks=len(chunks), entities=len(graph["entities"]), relationships=len(graph["relationships"]), concepts=len(graph["concepts"]))

    def _save_graph(self, book_id: str, graph: dict[str, object]) -> None:
        self._graph_root.mkdir(parents=True, exist_ok=True)
        target = self._graph_root / f"{sha256(book_id.encode('utf-8')).hexdigest()}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)


def _chapters(documents) -> list[dict[str, object]]:
    chapters = []
    current = "Opening"
    for document in documents:
        if document.chapter_title or re.match(r"^(chapter|book|part)\b", document.text.strip(), re.I):
            current = document.chapter_title or document.text.splitlines()[0][:120]
            chapters.append({"title": current, "start_page": document.page_number})
    return chapters or [{"title": current, "start_page": 1}]


def _chapter_for(page: int, chapters: list[dict[str, object]]) -> str:
    return [item["title"] for item in chapters if item["start_page"] <= page][-1]


def _base(book_id, page, source, entities, relationships):
    return {"interval_id": f"{book_id}:interval:{(page - 1) // 2}", "start_time": float(page), "end_time": float(page), "entities": tuple(entities), "relationships": tuple(f"{item['subject']} {item['predicate']} {item['object']}" for item in relationships), "source": source}


def _append(chunks, kind, text, identifier, base):
    cleaned = " ".join((text or "").split())[:900]
    if cleaned:
        chunks.append(SemanticChunk(id=identifier, kind=kind, text=cleaned, **base))


def _append_many(chunks, kind, texts, source, base):
    for index, text in enumerate(texts):
        _append(chunks, kind, text, f"{source}:{kind}:{index}", base)


def _text(payload, key):
    value = payload.get(key, "") if isinstance(payload, dict) else ""
    return value if isinstance(value, str) else ""


def _texts(payload, key):
    value = payload.get(key, []) if isinstance(payload, dict) else []
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _items(payload, key):
    value = payload.get(key, []) if isinstance(payload, dict) else []
    return [item for item in value if isinstance(item, dict) and all(isinstance(value, str) and value for value in item.values())] if isinstance(value, list) else []


def _names(payload, key):
    return [item["name"] for item in _items(payload, key) if "name" in item]


def _relationships(payload):
    return [item for item in _items(payload, "relationships") if {"subject", "predicate", "object"}.issubset(item)]
