"""Model-independent contract for deterministic accessibility reasoning."""
from abc import ABC, abstractmethod

from schemas.accessibility_reasoning import AccessibilityReasoningRequest, AccessibilityReasoningResult


class AccessibilityReasoner(ABC):
    """Transforms verified knowledge into accessible structured UI content without GPT."""

    @abstractmethod
    def reason(self, request: AccessibilityReasoningRequest) -> AccessibilityReasoningResult:
        """Return profile-adapted content based only on supplied knowledge facts."""
