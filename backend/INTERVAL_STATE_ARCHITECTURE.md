# IntervalState ownership

`IntervalState` is MagiFab's only browser-facing playback object. Movie load
preprocesses every fixed 30-second interval in chronological order. Each
`POST /api/v1/companion/prepare` call samples one interval and persists its
frozen snapshot. Playback and seeking only select that stored snapshot by
timestamp; they never invoke semantic reasoning or prompt generation.

`POST /api/v1/companion/respond` loads the already-persisted snapshot and may
return a transient prompt answer beside its immutable prompt set. A missing
snapshot is a preprocessing failure (409), not a fallback to live generation.

## Field ownership

| Field | Owner | Consumers |
| --- | --- | --- |
| `metadata` | interval assembly in `CompanionPipelineService` | all UI surfaces; identifies the exact movie interval and knowledge revision |
| `metadata.interval_id`, `start_time`, `end_time`, `interval_number` | fixed 30-second `IntervalStateRepository` boundary | cache invalidation and time-aware rendering |
| `metadata.catalog_scene_id`, `movie_id`, `knowledge_revision` | optional catalog enrichment and interval assembly | diagnostics; never playback identity |
| `prompts.prompt_bubbles` | prompt ranking over the resolved story interval | prompt panel and bubbles |
| `prompts.prompt_answers` | prompt-response assembly | companion bubble/widget |
| `prompts.suggested_questions` | prompt ranking | future question affordances |
| `visualDrawer` | `StoryStatePresenter` projection copied into the snapshot | Visual Drawer only |
| `storyState` | `StoryStatePresenter` projection copied into the snapshot | story summary and timeline context |
| `characters` | presenter-derived active characters | character cards |
| `relationships` | resolved story relationships | relationship cards and drawer |
| `memory` | resolved story memory reminders | memory UI |
| `conversationContext` | current scene explanation and simplified dialogue | companion response text |
| `accessibilityHints` | profile-adapted vocabulary and emotion guidance | accessibility affordances |
| `semanticMemoryBefore` | frozen cumulative memory before the interval | preprocessing validation and traceability |
| `semanticMemoryAfter` | frozen cumulative memory after the interval | all interval reconstruction and validation |
| `cacheMetadata` | interval assembly | cache provenance and semantic revision diagnostics |

`PreprocessingStoryBuilder` and `TimelineMemoryService` are chronological
construction aids used only while generating IntervalStates. They are not API
contracts and are never consulted during playback. `IntervalStateRepository`
is the runtime store: it validates interval identity/range and retrieves an
immutable snapshot for any timestamp without forward-only assumptions.

There are no public drawer, live-story, character-card, timeline, or prompt
response envelopes. The two companion endpoints each serialize a single
`IntervalState` object at their response root. A prompt answer is represented
only by `prompts.prompt_answers` on a response copy; it never changes the
persisted interval or duplicates any other display field.

`cacheMetadata` is immutable provenance attached to the interval. It does not
own state and cannot be used as a separate playback response.

Semantic reuse and cache bookkeeping are telemetry, not story events. They are
discarded before StoryState presentation and every display list in an
`IntervalState` is normalized to unique user-facing entries.

## Write/read rules

- Prompt generation creates a new `IntervalState.prompts` value; it does not
  write independent prompt history or a separate prompt payload.
- Prompt answers are a transient copy whose `prompt_answers` is populated;
  the stored interval snapshot and its prompt list are never modified.
- Visual Drawer, character cards, story summary, timeline, and memory are
  read-only consumers of their respective `IntervalState` fields.
- The frontend stores one active `IntervalState` and passes it unchanged to
  all screen elements. It never joins fragmented backend responses.

## Playback retrieval rules

The frontend cache is populated only by preprocessing. During playback it
calculates `floor(timestamp / 30)`, unloads the previously active snapshot,
and loads the matching immutable snapshot from that cache. Rewinding and
seeking follow the same lookup: there is no interpolation, prompt generation,
StoryState generation, or Visual Drawer generation in the playback path.

Preprocessing is the only chronological process. Its temporary
`PreprocessingStoryBuilder` rejects out-of-order generation so an interval can
be derived from the correct preceding narrative context. That check does not
exist in `IntervalStateRepository.load()` and cannot run during playback.

The only live companion request is a prompt answer. It identifies the active
interval, retrieves the persisted snapshot server-side, and returns a
transient answer in `prompts.prompt_answers`; the cached snapshot is not
replaced or mutated.

## Catalog enrichment rule

Catalog scene IDs are optional annotations supplied to vision and semantic
matching. They may add names, events, or emotional context, but cannot create,
remove, or reset runtime memory. Every internal observation and claim is keyed
by the fixed interval ID. When annotations end, preprocessing continues with
vision plus `semanticMemoryAfter` from the preceding interval; known
characters, relationships, goals, objects, emotions, and unresolved threads
remain until explicit semantic evidence changes them. Missing metadata is
therefore never an empty interval and never blocks playback by itself.
