from services.retrieval_validation import RetrievalValidator
from services.semantic_retrieval import RetrievedChunk, SemanticChunk


def _chunk(identifier: str, kind: str, text: str, score: float, entities=()):
    return RetrievedChunk(SemanticChunk(identifier, kind, text, "book:interval:0", 1, 1, entities, (), "page:1"), score)


def test_definition_validation_rejects_chunks_without_the_named_term():
    result = RetrievalValidator().validate("What is a Gom Jabbar?", "definition", [_chunk("generic", "paragraph", "Paul is tested by a mysterious woman.", .96, ("Paul",))])

    assert not result.passed
    assert "named term" in result.reason


def test_definition_validation_accepts_evidence_containing_the_named_term():
    result = RetrievalValidator().validate("What is a Gom Jabbar?", "definition", [_chunk("definition", "glossary", "Gom Jabbar: a poison needle used in the test.", .82)])

    assert result.passed
