"""Application service for the language-only GPT personalization boundary."""
from models.language_personalizer import LanguagePersonalizer
from schemas.personalization import GPTPersonalizationRequest, GPTPersonalizationResponse


class GPTPersonalizationService:
    """Delegates wording only; semantic reasoning and perception remain outside this service."""

    def __init__(self, personalizer: LanguagePersonalizer):
        self._personalizer = personalizer

    def personalize(self, request: GPTPersonalizationRequest) -> GPTPersonalizationResponse:
        response, model = self._personalizer.personalize(request)
        return GPTPersonalizationResponse(response=response, model=model)
