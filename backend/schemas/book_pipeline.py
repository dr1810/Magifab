"""Public contracts for the separate, text-only MagiFab book pipeline."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from schemas.movie_pipeline import CompanionProfilePayload


class BookProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    companion_profile: CompanionProfilePayload = Field(default_factory=CompanionProfilePayload)


class BookUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    book_id: str
    status: str
    reused_existing: bool


class BookProcessingStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    progress: str
    percentage: int = Field(ge=0, le=100)
    error: str | None = None


class BookPreprocessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    book_id: str
    status: str
    accepted: bool


class BookChapterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chapter: int
    title: str
    summary: str
    characters: list[dict[str, str]]
    relationships: list[str]
    locations: list[str]
    politicalSocialContext: list[str]
    memoryAids: list[str]
    timeline: list[str]
    glossary: list[dict[str, str]]
    visualRelationshipMap: dict[str, object]


class BookChatRequest(BookProfileRequest):
    chapter: int = Field(ge=1)
    question: str = Field(min_length=1, max_length=4_000)


class BookChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    chapter: int
