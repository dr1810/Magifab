"""Read-only graph traversal over a SemanticMovieKnowledge record."""
from schemas.knowledge import SemanticMovieKnowledge, SceneSummary, TimelinePosition


class MovieKnowledgeGraph:
    """Exposes scene and timeline lookup without embedding storage or matching concerns."""

    def __init__(self, knowledge: SemanticMovieKnowledge):
        self._knowledge = knowledge

    def scene(self, scene_id: str | None, timestamp_seconds: float | None) -> SceneSummary | None:
        if scene_id:
            explicit_scene = next((scene for scene in self._knowledge.scene_summaries if scene.scene_id == scene_id), None)
            if explicit_scene is not None:
                return explicit_scene
        if timestamp_seconds is None:
            return None
        return next((scene for scene in self._knowledge.scene_summaries if scene.start_seconds <= timestamp_seconds <= scene.end_seconds), None)

    def timeline_position(self, timestamp_seconds: float | None) -> TimelinePosition | None:
        if timestamp_seconds is None:
            return None
        return next((position for position in self._knowledge.timeline_positions if position.start_seconds <= timestamp_seconds <= position.end_seconds), None)
