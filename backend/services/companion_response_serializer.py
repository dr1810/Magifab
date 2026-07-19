"""Public serialization of the one immutable IntervalState contract."""
from schemas.companion_pipeline import IntervalPreparationResponse
from schemas.interval_state import IntervalState


class CompanionResponseSerializer:
    """Never receives or inspects model output, observations, perception, or graph objects."""

    def prepare(
        self,
        *,
        interval_state: IntervalState,
    ) -> IntervalPreparationResponse:
        return IntervalPreparationResponse.model_validate(interval_state.model_dump(mode="json"))
