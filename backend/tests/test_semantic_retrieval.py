from services.semantic_retrieval import SemanticChunk, SemanticRetrievalIndex


class SemanticFakeEmbeddings:
    def embed_documents(self, texts):
        return [self._vector(text) for text in texts]

    def embed_query(self, text):
        return self._vector(text)

    @staticmethod
    def _vector(text):
        normalized = text.casefold()
        if "gom jabbar" in normalized or "poison needle" in normalized:
            return (1.0, 0.0, 0.0)
        if "reverend mother" in normalized or "bene gesserit" in normalized:
            return (0.0, 1.0, 0.0)
        return (0.0, 0.0, 1.0)


def test_retrieval_returns_only_semantically_ranked_evidence_chunks(tmp_path):
    index = SemanticRetrievalIndex(tmp_path, SemanticFakeEmbeddings())
    chunks = (
        SemanticChunk("book:p1:paragraph:0", "paragraph", "The Reverend Mother tests Paul with a poison needle called a Gom Jabbar.", "book:interval:0", 1, 1, ("Paul", "Reverend Mother"), (), "page:1"),
        SemanticChunk("book:p10:paragraph:0", "paragraph", "The Duke discusses Arrakis with his advisors.", "book:interval:4", 10, 10, ("Duke",), (), "page:10"),
        SemanticChunk("book:p20:paragraph:0", "paragraph", "A desert storm changes the journey.", "book:interval:9", 20, 20, (), (), "page:20"),
    )
    index.build("book", [], chunks)

    result = index.retrieve("book", "What is a Gom Jabbar?", current_interval_id="book:interval:9", allowed_kinds=("paragraph",), limit=2)

    assert [chunk.id for chunk in result] == ["book:p1:paragraph:0", "book:p20:paragraph:0"]
    assert result[0].text == "The Reverend Mother tests Paul with a poison needle called a Gom Jabbar."
    assert all(len(chunk.text) < 900 for chunk in result)


def test_retrieval_survives_index_reload(tmp_path):
    chunks = (SemanticChunk("movie:s1:character:0", "character", "Victoria is Ellie's sister.", "movie:interval:0", 0, 30, ("Victoria", "Ellie"), ("siblings",), "interval:movie:interval:0"),)
    SemanticRetrievalIndex(tmp_path, SemanticFakeEmbeddings()).build("movie", [], chunks)

    result = SemanticRetrievalIndex(tmp_path, SemanticFakeEmbeddings()).retrieve("movie", "Who is Victoria?", current_interval_id="movie:interval:0", allowed_kinds=("character",))

    assert result[0].id == "movie:s1:character:0"
