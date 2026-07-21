"""Public contracts for the separate, text-only MagiFab book pipeline."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BookCompanionProfilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    personality: str = "warm"
    accessibility_needs: list[str] = Field(default_factory=list)
    difficulties: list[str] = Field(default_factory=list)
    preferred_explanation_style: str = "simple"


class BookProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    companion_profile: BookCompanionProfilePayload = Field(default_factory=BookCompanionProfilePayload)


class BookUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    book_id: str
    status: str
    reused_existing: bool


class BookChapterMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chapter_number: int = Field(ge=1)
    chapter_title: str
    section_label: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)


class BookChaptersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    book_id: str
    chapters: list[BookChapterMetadata]


class BookProcessingStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    progress: str
    percentage: int = Field(ge=0, le=100)
    error: str | None = None
    chapter_count: int = Field(default=0, ge=0)


class BookPreprocessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    book_id: str
    status: str
    accepted: bool


class BookCharacter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str


class BookRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    relation: str
    target: str


class VisualMapNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str


class VisualMapEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    target: str
    label: str


class VisualRelationshipMap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: list[VisualMapNode] = Field(default_factory=list)
    edges: list[VisualMapEdge] = Field(default_factory=list)


class CompanionQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    question: str


class BookChapterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chapter_number: int = Field(ge=1)
    chapter_title: str
    section_label: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    chapter_summary: str
    simple_explanation: str
    characters: list[BookCharacter] = Field(default_factory=list)
    relationships: list[BookRelationship] = Field(default_factory=list)
    important_events: list[str] = Field(default_factory=list)
    difficult_concepts: list[str] = Field(default_factory=list)
    memory_aid: str
    visual_relationship_map: VisualRelationshipMap
    companion_questions: list[CompanionQuestion] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class BookChatRequest(BookProfileRequest):
    chapter: int = Field(ge=1)
    question: str = Field(min_length=1, max_length=4_000)


class BookChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    chapter_number: int
