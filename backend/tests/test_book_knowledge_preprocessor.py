from pathlib import Path

from models.book_semantic_extractor import BookSemanticExtractor
from schemas.book_knowledge import BookIngestionRequest, BookPageSource
from services.book_knowledge_preprocessor import BookKnowledgePreprocessor


class FakeBookExtractor(BookSemanticExtractor):
    def extract(self, *, paragraph, page_number, chapter_title):
        if "Gom Jabbar" in paragraph:
            return {
                "summary": "The Reverend Mother tests Paul.",
                "entities": [{"name": "Paul", "kind": "character", "description": "A young man being tested."}, {"name": "Reverend Mother", "kind": "character", "description": "A Bene Gesserit examiner."}],
                "relationships": [{"subject": "Reverend Mother", "predicate": "tests", "object": "Paul"}],
                "definitions": [{"term": "Gom Jabbar", "definition": "A poison needle used in the test."}],
                "concepts": [{"name": "Bene Gesserit", "kind": "organization", "description": "An influential order."}],
                "events": ["Paul undergoes the test."],
                "quotes": ["Gom Jabbar"],
            }
        return {"summary": "Paul reflects on the test.", "entities": [{"name": "Paul", "kind": "character", "description": "A young man."}], "relationships": [], "definitions": [], "concepts": [], "events": ["Paul remembers the test."], "quotes": []}


class CapturingIndex:
    def __init__(self):
        self.calls = []

    def build(self, work_id, states, extra_chunks=()):
        self.calls.append((work_id, states, extra_chunks))


def test_full_book_preprocessing_builds_global_graph_and_semantic_chunks(tmp_path: Path):
    index = CapturingIndex()
    service = BookKnowledgePreprocessor(FakeBookExtractor(), index, tmp_path)
    request = BookIngestionRequest(
        book_id="dune", expected_pages=2,
        pages=[
            BookPageSource(page_number=1, text="Chapter One\n\nThe Reverend Mother gives Paul the Gom Jabbar test."),
            BookPageSource(page_number=2, text="Paul reflects on the test afterward."),
        ],
    )

    result = service.preprocess(request)

    chunks = index.calls[0][2]
    kinds = {chunk.kind for chunk in chunks}
    assert result.pages_processed == 2
    assert result.entities == 2
    assert result.relationships == 1
    assert {"paragraph", "character", "relationship", "glossary", "lore", "event", "quote", "chapter"}.issubset(kinds)
    assert any(chunk.text.startswith("Gom Jabbar:") for chunk in chunks)
    assert list(tmp_path.glob("*.json"))
