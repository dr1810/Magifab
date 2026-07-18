"""Schemas for GPT language personalization over already-verified structured facts."""
from pydantic import BaseModel, ConfigDict, Field

from schemas.accessibility_reasoning import (
    AccessibilityProfile,
    AccessibilityReasoningResult,
    CompanionProfile,
)
from schemas.reasoning_context import ReasoningContext


class GPTPersonalizationRequest(BaseModel):
    """No image, detection, or matching input is accepted by the GPT boundary."""
    model_config = ConfigDict(extra="forbid")
    user_message: str = Field(min_length=1, max_length=2_000)
    reasoning_context: ReasoningContext
    accessibility_content: AccessibilityReasoningResult
    accessibility_profile: AccessibilityProfile
    companion_profile: CompanionProfile


class GPTPersonalizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response: str = Field(min_length=1)
    model: str
