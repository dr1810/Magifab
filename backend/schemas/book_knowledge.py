"""Whole-book ingestion contract; every page must be supplied before readiness."""
from pydantic import BaseModel, ConfigDict, Field, model_validator


class BookPageSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=100_000)


class BookIngestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    book_id: str = Field(min_length=1)
    expected_pages: int = Field(ge=1)
    pages: list[BookPageSource] = Field(min_length=1)

    @model_validator(mode="after")
    def complete_page_set(self) -> "BookIngestionRequest":
        numbers = {page.page_number for page in self.pages}
        if numbers != set(range(1, self.expected_pages + 1)):
            raise ValueError("all_book_pages_are_required")
        return self


class BookKnowledgeIngestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    book_id: str
    pages_processed: int
    chapters_detected: int
    semantic_chunks: int
    entities: int
    relationships: int
    concepts: int
