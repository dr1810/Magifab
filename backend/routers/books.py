"""Separate upload-once, stored-artifact APIs for books."""
from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status

from app import get_book_pipeline_service
from schemas.book_pipeline import (
    BookChatRequest,
    BookChatResponse,
    BookChapterResponse,
    BookChaptersResponse,
    BookPreprocessResponse,
    BookProcessingStatusResponse,
    BookProfileRequest,
    BookUploadResponse,
)
from services.example_books import get_example_book_path
from services.book_pipeline_service import BookPipelineService

router = APIRouter(prefix="/api/v1/books", tags=["book preprocessing"])
logger = logging.getLogger(__name__)


@router.get("/examples/dune")
def dune_example(service: BookPipelineService = Depends(get_book_pipeline_service)) -> dict[str, str]:
    return _resolve_example("dune", service)


@router.get("/examples/{example_name}")
def named_example(example_name: str, service: BookPipelineService = Depends(get_book_pipeline_service)) -> dict[str, str]:
    return _resolve_example(example_name, service)


def _resolve_example(example_name: str, service: BookPipelineService) -> dict[str, str]:
    try:
        source = get_example_book_path(example_name)
    except FileNotFoundError as error:
        logger.warning("Example lookup failed for '%s': %s", example_name, error)
        raise HTTPException(
            status_code=404,
            detail={
                "message": "The requested example is unavailable in bundled backend assets.",
                "example": example_name,
                "error": str(error),
            },
        ) from error
    title = "Dune" if example_name.casefold() == "dune" else source.stem
    book_id = service.register_example(source, title=title)
    if not book_id:
        logger.warning("Example source path was resolved but file could not be registered: %s", source)
        raise HTTPException(
            status_code=404,
            detail={
                "message": "The requested example path was resolved but the file could not be loaded.",
                "example": example_name,
                "resolved_path": str(source),
            },
        )
    return {"book_id": book_id}


@router.post("/upload", response_model=BookUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_book(book: UploadFile = File(...), title: str | None = Form(default=None), service: BookPipelineService = Depends(get_book_pipeline_service)) -> BookUploadResponse:
    allowed = {"application/pdf", "text/plain", "application/epub+zip"}
    if book.content_type not in allowed and not (book.filename or "").lower().endswith((".pdf", ".txt", ".epub")):
        raise HTTPException(status_code=415, detail="Upload a PDF, EPUB, or text file.")
    suffix = Path(book.filename or "book.pdf").suffix
    with NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        while block := await book.read(1024 * 1024): temporary.write(block)
    try:
        if temporary_path.stat().st_size == 0: raise HTTPException(status_code=422, detail="The uploaded book is empty.")
        return BookUploadResponse(**service.upload(temporary_path, book.filename or "book", book.content_type or "application/octet-stream", title))
    finally:
        await book.close(); temporary_path.unlink(missing_ok=True)


@router.post("/{book_id}/preprocess", response_model=BookPreprocessResponse, status_code=status.HTTP_202_ACCEPTED)
def preprocess(book_id: str, tasks: BackgroundTasks, request: BookProfileRequest = BookProfileRequest(), service: BookPipelineService = Depends(get_book_pipeline_service)) -> BookPreprocessResponse:
    try: accepted = service.start(book_id)
    except KeyError as error: raise HTTPException(status_code=404, detail="Book was not found.") from error
    if accepted: tasks.add_task(service.preprocess, book_id, request.companion_profile.model_dump(mode="json"))
    return BookPreprocessResponse(book_id=book_id, status="extracting" if accepted else service.status(book_id).status, accepted=accepted)


@router.get("/{book_id}/processing-status", response_model=BookProcessingStatusResponse)
def processing_status(book_id: str, service: BookPipelineService = Depends(get_book_pipeline_service)) -> BookProcessingStatusResponse:
    try: return service.status(book_id)
    except KeyError as error: raise HTTPException(status_code=404, detail="Book was not found.") from error


@router.get("/{book_id}/chapters", response_model=BookChaptersResponse)
def chapters(book_id: str, service: BookPipelineService = Depends(get_book_pipeline_service)) -> BookChaptersResponse:
    try:
        return service.chapters(book_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Book was not found.") from error


@router.get("/{book_id}/chapter", response_model=BookChapterResponse)
def chapter(book_id: str, chapter: int = 1, service: BookPipelineService = Depends(get_book_pipeline_service)) -> BookChapterResponse:
    try: return service.chapter(book_id, chapter)
    except KeyError as error: raise HTTPException(status_code=404, detail="Book was not found.") from error
    except ValueError as error: raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/{book_id}/companion/chat", response_model=BookChatResponse)
def chat(book_id: str, request: BookChatRequest, service: BookPipelineService = Depends(get_book_pipeline_service)) -> BookChatResponse:
    try:
        answer, chapter_number = service.answer(book_id, request.chapter, request.question)
        return BookChatResponse(answer=answer, chapter_number=chapter_number)
    except KeyError as error: raise HTTPException(status_code=404, detail="Book was not found.") from error
    except ValueError as error: raise HTTPException(status_code=409, detail=str(error)) from error
