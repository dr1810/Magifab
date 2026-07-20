"""Whole-book ingestion endpoint; page-level UI preparation never calls this."""
from fastapi import APIRouter, Depends, HTTPException, status

from adapters.openai_personalizer import PersonalizationConfigurationError, PersonalizationProviderError
from app import get_book_knowledge_preprocessor
from schemas.book_knowledge import BookIngestionRequest, BookKnowledgeIngestionResult
from services.book_knowledge_preprocessor import BookKnowledgePreprocessor

router = APIRouter(prefix="/api/v1/books", tags=["book knowledge"])


@router.post("/ingest", response_model=BookKnowledgeIngestionResult, status_code=status.HTTP_201_CREATED)
def ingest_book(request: BookIngestionRequest, service: BookKnowledgePreprocessor = Depends(get_book_knowledge_preprocessor)) -> BookKnowledgeIngestionResult:
    """Process every normalized/OCR page into a complete book knowledge base."""
    try:
        return service.preprocess(request)
    except PersonalizationConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Gemini book ingestion is not configured") from error
    except PersonalizationProviderError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Gemini book extraction is unavailable") from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Book ingestion input is incomplete") from error
