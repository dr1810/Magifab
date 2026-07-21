"""Durable, text-only book processing. It deliberately shares no movie/video code."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
from uuid import uuid4

from schemas.book_pipeline import BookChapterResponse, BookProcessingStatusResponse


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
        data[book_id] = {"id": book_id, "hash": digest, "title": title or Path(filename).stem, "filename": Path(filename).name, "mime_type": mime_type, "source": str(target), "status": "queued", "progress": "Waiting to process", "percentage": 0, "error": None}
        self._write(data); return {"book_id": book_id, "status": "queued", "reused_existing": False}

    def start(self, book_id: str) -> bool:
        data = self._read(); book = self._book(data, book_id)
        if book["status"] == "complete": return False
        if book["status"] in {"extracting", "understanding", "reasoning"}: return False
        book.update(status="extracting", progress="Extracting text", percentage=5, error=None); self._write(data); return True

    def preprocess(self, book_id: str, profile: dict[str, object] | None = None) -> None:
        data = self._read(); book = self._book(data, book_id)
        try:
            text = self._extract(Path(book["source"]))
            if not text.strip(): raise ValueError("No readable text was found in this book.")
            book.update(status="understanding", progress="Understanding chapters", percentage=35); self._write(data)
            chapters = self._chapters(text)
            book.update(status="reasoning", progress="Building character relationships and accessibility explanations", percentage=70); self._write(data)
            artifacts = [self._artifact(index + 1, title, content, profile or {}) for index, (title, content) in enumerate(chapters)]
            target = self.root / "artifacts" / f"{book_id}.json"; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(artifacts, ensure_ascii=False), encoding="utf-8")
            book.update(status="complete", progress="Reading companion is ready", percentage=100, artifact=str(target)); self._write(data)
        except Exception as error:
            current_percentage = int(book.get("percentage", 0)) if isinstance(book.get("percentage"), int) else 0
            book.update(status="failed", progress="Processing failed", percentage=max(current_percentage, 5), error=str(error)); self._write(data)

    def status(self, book_id: str) -> BookProcessingStatusResponse:
        book = self._book(self._read(), book_id)
        return BookProcessingStatusResponse(status=book["status"], progress=book["progress"], percentage=book["percentage"], error=book.get("error"))

    def chapter(self, book_id: str, chapter: int) -> BookChapterResponse:
        book = self._book(self._read(), book_id)
        if book["status"] != "complete": raise ValueError("Book artifacts are not ready.")
        artifacts = json.loads(Path(book["artifact"]).read_text(encoding="utf-8"))
        if not artifacts: raise ValueError("No chapters were generated.")
        return BookChapterResponse.model_validate(artifacts[min(chapter - 1, len(artifacts) - 1)])

    def answer(self, book_id: str, chapter: int, question: str) -> tuple[str, int]:
        artifact = self.chapter(book_id, chapter)
        lower = question.lower()
        if "who" in lower and artifact.characters: return "; ".join(f"{x['name']}: {x['description']}" for x in artifact.characters[:3]), artifact.chapter
        if "relationship" in lower: return " ".join(artifact.relationships) or artifact.summary, artifact.chapter
        if "remember" in lower: return "Remember: " + " ".join(artifact.memoryAids), artifact.chapter
        return artifact.summary, artifact.chapter

    def register_example(self, source: Path) -> str | None:
        if not source.is_file(): return None
        return str(self.upload(source, source.name, "application/pdf", "Dune")["book_id"])

    def example_id(self, title: str) -> str | None:
        for book in self._read().values():
            if str(book.get("title", "")).casefold() == title.casefold():
                return str(book["id"])
        return None

    def _extract(self, source: Path) -> str:
        if source.suffix.lower() == ".pdf":
            from pypdf import PdfReader
            return "\n".join(page.extract_text() or "" for page in PdfReader(str(source)).pages)
        if source.suffix.lower() == ".epub":
            import zipfile
            with zipfile.ZipFile(source) as archive:
                return "\n".join(re.sub(r"<[^>]+>", " ", archive.read(name).decode("utf-8", "ignore")) for name in archive.namelist() if name.lower().endswith((".xhtml", ".html", ".htm")))
        return source.read_text(encoding="utf-8", errors="replace")

    def _chapters(self, text: str) -> list[tuple[str, str]]:
        parts = re.split(r"(?im)^\s*((?:chapter|book|part)\s+[\w .'-]+)\s*$", text)
        result: list[tuple[str, str]] = []
        if len(parts) > 1:
            opening = parts[0].strip()
            if opening: result.append(("Opening", opening))
            for index in range(1, len(parts) - 1, 2): result.append((parts[index].strip(), parts[index + 1].strip()))
        if not result:
            size = 12000
            result = [(f"Section {index // size + 1}", text[index:index + size]) for index in range(0, len(text), size)]
        return [(title, body) for title, body in result if body.strip()][:80]

    def _artifact(self, number: int, title: str, text: str, profile: dict[str, object]) -> dict[str, object]:
        if self.reasoner is not None:
            return self.reasoner.reason(number, title, text, profile).model_dump(mode="json")
        clean = " ".join(text.split())
        names = list(dict.fromkeys(re.findall(r"\b[A-Z][a-z]{2,}\b", clean)))[:12]
        locations = list(dict.fromkeys(re.findall(r"\b(?:on|in|at) ([A-Z][A-Za-z -]{2,})", clean)))[:8]
        glossary = [{"term": term, "definition": "A story term explained in the surrounding chapter."} for term in names[:8]]
        focus = ", ".join(profile.get("accessibility_needs", []) if isinstance(profile.get("accessibility_needs"), list) else [])
        summary = clean[:1600] or "This section has very little extractable text."
        return {"chapter": number, "title": title[:160], "summary": summary, "characters": [{"name": name, "description": f"Appears in {title}."} for name in names], "relationships": [f"{names[0]} and {names[1]} are both important in this section." ] if len(names) > 1 else [], "locations": locations, "politicalSocialContext": [f"This explanation is tailored for: {focus}." ] if focus else [], "memoryAids": [summary[:260]], "timeline": [f"Chapter {number}: {title}"], "glossary": glossary, "visualRelationshipMap": {"nodes": names, "edges": [[names[0], names[1]]] if len(names) > 1 else []}}

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
