"""Model-independent contract for deterministic accessibility reasoning."""
from abc import ABC, abstractmethod

from schemas.accessibility_presentation import AccessibilityPresentation
from schemas.accessibility_reasoning import AccessibilityReasoningRequest


class AccessibilityReasoner(ABC):
    """Transforms verified knowledge into accessible structured UI content without GPT."""

    @abstractmethod
    def reason(self, request: AccessibilityReasoningRequest) -> AccessibilityPresentation:
        """Return profile-adapted content based only on supplied knowledge facts."""
