"""Presentation-only serialization for companion API responses."""
from schemas.accessibility_presentation import AccessibilityPresentation
from schemas.accessibility_reasoning import AccessibilityDrawerContent, AccessibilityReasoningResult, CompanionProfile
from schemas.companion_pipeline import PreparationCacheMetadata, PreparedPromptBubble, ScenePreparationResponse


class CompanionResponseSerializer:
    """Never receives or inspects model output, observations, perception, or graph objects."""

    def content(self, presentation: AccessibilityPresentation, companion: CompanionProfile) -> AccessibilityReasoningResult:
        return AccessibilityReasoningResult(
            companion_tone=f"{companion.personality}; {companion.conversation_style}",
            scene_summary=presentation.scene_explanation,
            likely_confusions=[],
            prompt_bubbles=presentation.prompt_bubbles,
            drawer=AccessibilityDrawerContent(
                character_cards=presentation.character_cards,
                relationship_summaries=presentation.relationship_summaries,
                timeline_summary=presentation.timeline_summary,
                emotion_summaries=presentation.emotion_summaries,
                memory_reminders=presentation.memory_reminders,
                vocabulary_assistance=presentation.vocabulary_assistance,
                conversation_simplifications=presentation.conversation_simplifications,
            ),
        )

    def prepare(
        self,
        *,
        presentation: AccessibilityPresentation,
        companion: CompanionProfile,
        knowledge_source: str,
        knowledge_revision: int,
        cache: PreparationCacheMetadata,
    ) -> ScenePreparationResponse:
        content = self.content(presentation, companion)
        return ScenePreparationResponse(
            knowledge_source=knowledge_source,
            knowledge_revision=knowledge_revision,
            presentation=presentation,
            # Compatibility aliases are derived exclusively from presentation.
            accessibility_content=content,
            scene_summary=presentation.scene_explanation,
            prompt_bubbles=[
                PreparedPromptBubble(
                    id=item.id,
                    type="who_is_that" if item.kind == "character" else item.kind,
                    title=item.label,
                    question=item.question,
                    text=item.label,
                    priority=item.priority,
                    claim_ids=item.claim_ids,
                )
                for item in presentation.prompt_bubbles
            ],
            visual_drawer=content.drawer,
            cache=cache,
        )
