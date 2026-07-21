from schemas.movie_pipeline import Confidence, EntityNeedingIdentification, GeminiVisualScene
from services.search_query_planner import SearchQueryPlanner


def test_search_query_planner_only_queries_supported_unresolved_entities():
    scene = GeminiVisualScene(
        scene_summary="A character walks past a tree toward a landmark.",
        entities_needing_identification=[
            EntityNeedingIdentification(entity="Unknown", kind="character", description="a masked performer wearing a silver cape", reason="identity not visible", certainty=Confidence.LOW),
            EntityNeedingIdentification(entity="Tree", kind="object", description="tree", reason="ordinary scenery", certainty=Confidence.LOW),
            EntityNeedingIdentification(entity="Unknown", kind="landmark", description="a distinctive clock tower with a blue dome", reason="location needs identification", certainty=Confidence.LOW),
        ],
    )

    planned = SearchQueryPlanner().build(scene, "Example Movie")

    assert len(planned) == 2
    assert all("tree" not in query.casefold() for _, query in planned)
    assert '"Example Movie"' in planned[0][1]
