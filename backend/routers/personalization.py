"""Server-side GPT personalization endpoint; clients never receive OpenAI credentials."""
from fastapi import APIRouter, Depends, HTTPException, status

from adapters.openai_personalizer import PersonalizationConfigurationError, PersonalizationProviderError
from app import get_gpt_personalization_service
from schemas.personalization import GPTPersonalizationRequest, GPTPersonalizationResponse
from services.gpt_personalization import GPTPersonalizationService

router = APIRouter(prefix="/api/v1", tags=["gpt personalization"])


@router.post("/personalize", response_model=GPTPersonalizationResponse)
def personalize(
    request: GPTPersonalizationRequest,
    service: GPTPersonalizationService = Depends(get_gpt_personalization_service),
) -> GPTPersonalizationResponse:
    """Convert verified facts to accessible language; no perception or semantic matching occurs here."""
    try:
        return service.personalize(request)
    except PersonalizationConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GPT personalization is not configured") from error
    except PersonalizationProviderError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GPT personalization is unavailable") from error
