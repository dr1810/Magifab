"""Canonical, cleaned book-page input for semantic reasoning."""
from pydantic import BaseModel, ConfigDict, Field


class CleanPageDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    content_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    chapter_title: str | None = None
    paragraphs: tuple[str, ...] = ()
    quotations: tuple[str, ...] = ()
    source_hash: str = Field(min_length=8)

    @property
    def text(self) -> str:
        return "\n\n".join(self.paragraphs)
