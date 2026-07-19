"""Structured accessibility reasoning endpoint with no language-model dependency."""
from fastapi import APIRouter, Depends

from app import get_accessibility_reasoning_engine
from schemas.interval_state import IntervalState
from schemas.accessibility_reasoning import AccessibilityReasoningRequest
from services.accessibility_reasoning import AccessibilityReasoningEngine

router = APIRouter(prefix="/api/v1/accessibility", tags=["accessibility reasoning"])


@router.post("/reason", response_model=IntervalState)
def reason(
    request: AccessibilityReasoningRequest,
    engine: AccessibilityReasoningEngine = Depends(get_accessibility_reasoning_engine),
) -> IntervalState:
    """Generate profile-adapted structured content from supplied verified knowledge only."""
    return engine.reason(request)
