"""Schedules prompts as semantic timeline objects at story-change boundaries."""
from schemas.story_state import StoryEvent, StoryState
from schemas.timeline_memory import TimelinePrompt


class PromptScheduler:
    def schedule(self, _state: StoryState, events: list[StoryEvent]) -> list[TimelinePrompt]:
        prompts = []
        for event in events:
            # Every semantic transition is candidate-worthy. Ranking later
            # decides prominence; scheduler must not erase interval context.
            if not event.is_new:
                continue
            label, question, kind = _copy(event)
            prompts.append(TimelinePrompt(
                prompt_id=f"timeline-prompt:{event.event_id}", start_timestamp=event.timestamp_start,
                priority=max(1, 5 - int(min(event.importance_score, 4))), activation_reason=event.event_type,
                semantic_event_id=event.event_id, claim_ids=event.semantic_claim_ids,
                label=label, question=question, kind=kind,
            ))
        # A resolved conflict or goal expires the related open prompt. No
        # expiry is inferred from window boundaries.
        if any(event.event_type in {"conflict_resolved", "goal_completed"} for event in events):
            for prompt in prompts:
                if prompt.activation_reason in {"conflict_begins", "goal_introduced"}:
                    prompt.end_timestamp = min(event.timestamp_start for event in events)
        return prompts


def _copy(event):
    mapping = {
        "character_introduced": ("Who is this character?", "Who is this new character, and why do they matter?", "character"),
        "emotion_changed": ("Why are they feeling this?", "What changed to cause this emotion?", "emotion"),
        "relationship_changed": ("Why does this connection matter?", "What changed in this relationship?", "relationship"),
        "conflict_begins": ("Why is this conflict important?", "What caused this conflict?", "scene"),
        "timeline_changed": ("Where are we in the story?", "What has led to this point?", "timeline"),
    }
    return mapping.get(event.event_type, ("What changed?", event.summary, "scene"))
