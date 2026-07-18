"""Presentation-only serialization for companion API responses."""
from schemas.accessibility_presentation import AccessibilityPresentation
from schemas.companion_pipeline import PreparationCacheMetadata, ScenePreparationResponse


class CompanionResponseSerializer:
    """Never receives or inspects model output, observations, perception, or graph objects."""

    def prepare(
        self,
        *,
        presentation: AccessibilityPresentation,
        knowledge_source: str,
        knowledge_revision: int,
        cache: PreparationCacheMetadata,
    ) -> ScenePreparationResponse:
        return ScenePreparationResponse(
            knowledge_source=knowledge_source,
            knowledge_revision=knowledge_revision,
            presentation=presentation,
            cache=cache,
        )
