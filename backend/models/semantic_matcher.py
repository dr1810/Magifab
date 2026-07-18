"""Model-independent contract for conservative semantic matching."""
from abc import ABC, abstractmethod

from schemas.fusion import UnifiedSceneRepresentation
from schemas.knowledge import SemanticMovieKnowledge
from schemas.matching import SemanticMatchResult


class SemanticMatcher(ABC):
    """Matches only supplied perception evidence to supplied movie knowledge."""

    @abstractmethod
    def match(self, scene: UnifiedSceneRepresentation, knowledge: SemanticMovieKnowledge) -> SemanticMatchResult:
        """Return verified facts; never manufacture a missing semantic fact."""
