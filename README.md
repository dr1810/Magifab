# MagiFab

MagiFab is a temporal AI accessibility companion for film. It helps a viewer understand a movie as a developing story: who is present, what changed, why an event matters, how relationships evolve, and what the current moment means in relation to everything that came before it.

This repository is an advanced research prototype. Its central premise is that accessible movie understanding cannot be solved by describing isolated frames. A useful companion needs to build a timestamped model of the movie while it is watched, preserve that model, and reason over it in a way that adapts to the viewer.

## Overview

Movies communicate through more than dialogue. Editing, performance, body language, repeated visual motifs, off-screen action, changes in music, and the return of a character or object all carry meaning. A conventional subtitle stream transcribes spoken words, but it does not explain why a character is suddenly afraid, why a new person matters, or how a scene connects to an earlier conflict.

That gap is especially consequential for viewers with cognitive and intellectual disabilities. A viewer may need support to:

- identify a character introduced without a spoken name;
- retain a relationship or motive across several scenes;
- understand a rapid emotional shift or visual cause-and-effect sequence;
- distinguish a meaningful plot event from background activity; and
- revisit story context without stopping the movie or navigating a dense interface.

MagiFab addresses these needs with an AI companion that maintains a growing semantic record of the film. It joins visual evidence with curated movie knowledge, grounds conclusions in timestamped semantic claims, and exposes only accessibility-oriented explanations to the viewer.

The result is not a generic image-captioning interface. It is a movie-aware system designed to answer questions at the right moment: *Who are these new characters? Why is Bunny suddenly angry? What led to this moment? Why is this object important?*

## Vision

MagiFab is not a subtitle system.

Subtitles are valuable, but they are a local representation: they tell the viewer what was said at a particular point in time. MagiFab is an adaptive story companion. It understands a movie over time, retains evidence from previous windows, and supplies concise assistance derived from the current moment and persistent movie memory.

The intended interaction is deliberately lightweight. Contextual prompt bubbles invite a viewer to request help when a story transition, new character, relationship change, emotion, or callback deserves explanation. A visual drawer acts as a live story assistant rather than a static scene panel. It can show the current scene, active characters, emotions, relationships, recent events, timeline position, important objects, reminders, and unresolved threads.

This approach treats accessibility as an inference problem. The question is not merely “what is visible now?” It is “what does the viewer need to know now, given what has already happened?”

## Architecture

MagiFab processes a movie as a sequence of bounded temporal observations and a persistent semantic memory:

```text
Movie
  ↓
Sliding Window
  ↓
Frame Understanding
  ↓
Object Detection (YOLO + Grounding DINO + Florence)
  ↓
Semantic Claims
  ↓
Story Event Extraction
↓
Story State Manager
↓
Accessibility Reasoning
  ↓
Prompt Bubble Generation
  ↓
Visual Drawer
```

### Movie

The movie is the source sequence. Playback time is a first-class input throughout the system. Every durable fact is tied to a timestamp interval and scene identifier; the system never treats a meaningful observation as timeless.

### Sliding Window

The sliding-window engine groups observations into bounded intervals rather than reasoning from one screenshot at a time. A window records its start and end timestamps, sampled frames, detected characters and objects, actions, events, emotions, relationships, and supporting claim IDs.

Windows enable change detection. The engine can distinguish a recurring background condition from a new character, an emotional transition, a relationship change, or a plot event. Seeking backwards resets short-term comparison state without discarding durable movie knowledge.

### Frame Understanding

Representative frames are decoded and validated before they enter the perception stack. Frame understanding is deliberately evidence-oriented: raw captions and detections are not sent directly to the accessibility UI. They are transformed into structured observations and then evaluated against movie knowledge.

### Object Detection

MagiFab combines multiple visual models because no single model is reliable enough for film understanding:

- **YOLO** provides fast, general-purpose object detections.
- **Grounding DINO** localizes text-guided entities when a relevant movie-world query is available.
- **Florence** contributes visual-language understanding for richer scene interpretation.

The perception fusion layer preserves source evidence and confidence. Detection output is useful input, not ground truth about a fictional world.

### Semantic Claims

Semantic claims are the system’s boundary between perception and reasoning. A claim is a graph-native assertion such as a character being present, an event occurring, a relationship changing, an emotion being relevant, or a timeline transition becoming active.

Each claim carries stable provenance: an ID, kind, scene ID, point timestamp, interval timestamps, confidence, observation IDs, evidence origin, knowledge references, and supporting claim IDs. This contract prevents the accessibility reasoner from depending on unverified visual prose.

### Story Event Extraction

The story-event extractor is the sole bridge from the semantic graph to narrative progression. It converts transient claims into typed `StoryEvent`s—character introductions and exits, emotion and relationship changes, conversation boundaries, location changes, important objects, conflict, goals, causes, effects, and scene transitions.

Every event has a stable ID, `timestamp_start`, `timestamp_end`, importance score, confidence, type, semantic claim IDs, entities, summary, novelty, memory requirement, and prompt requirement. StoryEvents, not semantic claims, are the source of all user-facing story timestamps.

For example, an event can be represented as:

```json
{
  "timestamp_start": 160.0,
  "timestamp_end": 170.0,
  "scene_id": "bbb-02",
  "description": "Rodents begin teasing Bunny",
  "confidence": 0.9,
  "supporting_claim_ids": ["bbb-event-rodents-tease"]
}
```

### Story State Manager

`StoryState` is MagiFab’s single source of truth. It is the only durable narrative memory and is updated atomically for each sliding window. It retains known characters, relationships, locations, and objects; current scene, timestamp, location, and goal; active emotions; recent events; story so far; open and resolved threads; reminders; and character, relationship, and timeline histories.

No renderer, prompt engine, or reasoner creates another story memory. Replaying a prepared window is idempotent: it preserves the same StoryEvent identity instead of duplicating story progression.

### Accessibility Reasoning

The accessibility reasoner works exclusively from semantic context and memory projections. It receives the current timestamp, semantic claims, active entities, history, relationship evolution, prior events, and timeline state—not raw pixels or model captions. This makes explanations traceable to claim IDs and keeps model hallucinations out of user-facing guidance.

### Prompt Bubble Generation

Prompt bubbles are generated from meaningful temporal change. They are ranked around new identities, significant events, relationship updates, emotional shifts, callbacks, timeline transitions, and vocabulary support. Every generated bubble has a timestamp interval, claim IDs, semantic event type, priority, and screen location.

The prompt layer also applies semantic cooldowns so a viewer is not repeatedly shown the same question while adjacent frames belong to the same story moment.

### Visual Drawer

The visual drawer is a live story assistant. It projects timestamped memory into an accessible, skimmable interface with:

- current scene and timestamp;
- active characters, emotions, and relationships;
- recent events and current story phase;
- story-so-far summaries and important objects;
- memory reminders; and
- unresolved story threads.

The drawer is a presentation of temporal memory, not a second inference pipeline.

## Core Components

| Component | Responsibility | Why it exists |
| --- | --- | --- |
| Sliding Window Engine | Aggregates frame-level semantic observations into bounded intervals and detects change from the preceding window. | Story meaning often emerges from a transition, not a single frame. |
| Story Event Extraction | Converts claims into timestamped, typed narrative events with explicit novelty and prompt/memory requirements. | It prevents semantic claims from becoming an implicit second story model. |
| Semantic Claims | Defines the typed boundary between perception, knowledge matching, and story-event extraction. | Prevents raw detector output from becoming ungrounded user-facing advice. |
| Story State Manager | Owns all durable events, characters, relationships, timelines, threads, reminders, and prompt history. | A single state prevents timeline and memory drift between components. |
| Persistent Character Memory | Is a `StoryState` projection that tracks character history, location, emotion, and important events. | A character’s meaning is cumulative. |
| Relationship Memory | Tracks first meeting, conflict, trust changes, alliances, and resolution through a timestamped history. | Relationships should evolve rather than remain static labels. |
| Timeline Memory | Retains ordered story phases and the viewer’s current position. | The companion must know whether the viewer is in setup, conflict, preparation, or resolution. |
| Prompt Bubble Engine | Converts temporal changes into focused, claim-backed questions. | Assistance should appear when it is useful, not as an indiscriminate stream of descriptions. |
| Visual Drawer | Presents a current memory snapshot as a live story assistant. | Viewers need a low-friction way to recover context. |
| Accessibility Reasoning | Produces explanations, reminders, summaries, and prompts from semantic memory only. | Accessibility reasoning needs continuity and verifiable evidence. |
| Caching | Stores prepared contexts, semantic knowledge, response data, and durable movie memory. | Makes playback interaction responsive and avoids repeating expensive inference. |
| Grounding DINO | Performs text-guided localization for known or queried entities. | General detectors often cannot identify movie-specific characters or objects. |
| Florence | Supplies visual-language interpretation to complement localization. | Many story-relevant conditions are contextual rather than simple object classes. |
| YOLO | Supplies efficient general object detection. | It provides a fast visual baseline for scene grounding. |

## How It Works

1. **Playback establishes the current movie time.** The client captures a representative frame for preparation rather than treating every prompt click as a fresh vision request.
2. **A sliding window is created.** The window anchors the frame in a bounded interval and compares it with the prior window to identify newly introduced entities and meaningful changes.
3. **Perception is fused.** YOLO, Grounding DINO, Florence, and optional verification adapters contribute evidence. The fusion layer retains model source and confidence instead of flattening all output into one caption.
4. **Movie knowledge is matched.** Curated scene, character, relationship, and timeline knowledge constrains the interpretation of perception evidence.
5. **Semantic claims are built.** The system emits typed assertions with provenance rather than passing detector labels onward.
6. **Story events are extracted.** Claims become timestamped events with entities, importance, novelty, and explicit memory/prompt requirements.
7. **StoryState is updated.** Existing characters, objects, relationships, goals, threads, histories, and timeline events are updated in one atomic state transition. The system does not recreate memory from the current frame.
8. **The accessibility reasoner reads StoryState only.** It can relate the current moment to prior events, character histories, relationship evolution, story progression, and unresolved threads without inspecting semantic claims.
9. **Prompt bubbles and drawer content are generated.** These are claim-backed accessibility presentations, not direct model output.
10. **Prepared context and response caches serve interaction.** A later question reads prepared semantic context and durable memory without re-running image understanding.

This accumulation model is the essential design choice. At 03:20, MagiFab should retain what it learned at 00:20 and 02:45. It should not rediscover the movie every ten seconds.

## Challenges Faced

Building a temporal movie companion required solving problems that do not appear in ordinary single-image applications.

### Movie preprocessing and synchronization

Video decoding, frame capture, scene identifiers, subtitles, movie knowledge, and playback time must agree. A small offset can attach an otherwise correct inference to the wrong story event. Cross-origin video handling also matters: browser canvas capture requires the media host to provide the right CORS headers.

### Sliding windows and context windows

Short windows are responsive but may miss slow developments; long windows retain more context but blur transitions and cost more to process. MagiFab separates bounded short-term comparison state from durable long-term memory so window size does not determine how much of the story is remembered.

### Temporal memory and memory consistency

Persistent memory must be append-oriented, idempotent, and safe under repeated preparation or playback seeks. Reobserving a fact should increase observation evidence rather than duplicate it. A backwards seek may reset local comparison state, but it must never erase a learned character or important event.

### Semantic grounding

Film footage contains fictional characters, stylized environments, occlusion, dramatic lighting, and rapid edits. A detector label is not enough to identify a character or infer a relationship. Semantic matching grounds visual evidence against movie-specific knowledge and records the origin of each conclusion.

### Object detection: YOLO, Grounding DINO, and Florence

YOLO is fast but limited by general object categories. Grounding DINO is powerful for text-guided localization but depends on suitable queries and can over-match visually similar regions. Florence provides useful visual-language information, but unconstrained captioning can hallucinate. MagiFab therefore treats each model as evidence, fuses sources, and keeps raw outputs outside accessibility reasoning.

### False detections and relationship validation

False detections are especially harmful in a narrative system because they can become false memories. Relationships are even more sensitive: visual proximity is not proof of friendship, conflict, fear, or alliance. Relationship updates are represented as grounded claims with timestamps and are only surfaced after semantic validation.

### Prompt generation

More prompts are not better prompts. The system must identify moments that deserve intervention, bind each bubble to claim IDs and a time interval, avoid prompt repetition, respect detail preferences, and still offer a useful fallback when a viewer needs help.

### Claim persistence, caching, and performance

Inference is expensive relative to a viewer’s interaction tolerance. Prepared scene contexts, semantic knowledge, memory snapshots, and response caches reduce unnecessary model calls. Cache keys are revision-aware so newer semantic knowledge does not silently receive stale explanations.

### Long-movie understanding and backend redesign

An isolated-scene pipeline cannot answer questions about progression. The backend was therefore redesigned around timestamped StoryEvents, a single persistent StoryState, sliding windows, and a retrieval-first interaction path. This changes the system from “explain a frame” to “maintain an understanding of a movie.”

## Iterations

MagiFab evolved through several deliberate redesigns. Each version addressed a limitation revealed by the previous one.

### Version 1 — Basic frame explanations

The first prototype described individual frames. It proved that visual assistance could be useful, but explanations were disconnected and could not retain characters, motives, or prior events.

### Version 2 — Semantic claim generation

The system moved from free-form descriptions to typed semantic claims. This introduced provenance, confidence, claim IDs, and a safer boundary between visual perception and accessibility output.

### Version 3 — Knowledge persistence

Movie knowledge, prepared contexts, and response caching were introduced so the system could reuse validated understanding and avoid expensive recomputation. This improved responsiveness but still treated most reasoning as scene-scoped.

### Version 4 — Sliding window reasoning

The engine began comparing bounded consecutive windows. This made it possible to recognize introductions, events, emotional changes, and relationship changes as differences over time instead of isolated visual facts.

### Version 5 — Timestamp architecture

Claims were converted into timestamped StoryEvents with scene IDs, confidence, entities, supporting claim IDs, and explicit memory/prompt requirements. Story progression became a first-class data structure rather than a request parameter.

### Version 6 — Persistent movie understanding

The current architecture adds durable character histories, relationship histories, global story timeline memory, important moments, unresolved threads, and a live story drawer. Each new window updates accumulated knowledge rather than rebuilding it.

## Design Decisions

### Why timestamped reasoning is superior

Timestamps turn observations into events. “Bunny is angry” is less useful than “Bunny becomes angry during this interval, after a preceding event, with these supporting claims.” Interval reasoning allows the system to order events, recognize returns and callbacks, calculate recency, and explain change.

### Why persistent memory is necessary

Narrative comprehension depends on retention. A character introduced at the beginning may matter much later; an object can become important only when it returns; a conflict may be resolved several scenes after it begins. Persistent memory gives the companion a stable semantic history without requiring the viewer to repeat context.

### Why accessibility requires previous events

For many viewers, the difficult part of a movie is not perceiving the current frame. It is connecting it to prior information. Remembering previous events enables explanations such as “this is the character introduced earlier,” “this reaction follows the earlier conflict,” or “this object is important because it appeared before.”

### Why isolated scene reasoning is insufficient

An isolated scene can identify objects and describe activity, but it cannot reliably infer stakes, emotional shifts, relationship evolution, or story position. It also encourages repetitive prompts and makes any missing visual evidence look like forgotten knowledge. MagiFab treats the frame as evidence for a continuing temporal model, not as the complete unit of meaning.

## Local Setup

### Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="server-side-only-key"
export OPENAI_MODEL="gpt-5.6" # optional
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Swagger is available at `http://127.0.0.1:8000/docs`.

### Frontend

```bash
npm install
npm run dev
```

Local `/api` requests are proxied to FastAPI on port 8000. For a deployed frontend, set `VITE_MAGIFAB_BACKEND_URL` to the public backend URL. Keep API keys on the backend; they must never be placed in browser-exposed environment files.

### Movie CORS

Frame capture draws the active video frame to a browser canvas. Configure the movie host with the policy in [config/r2-cors.json](config/r2-cors.json) and serve media with appropriate CORS headers. The player uses anonymous cross-origin requests, so the media host must allow the viewer origin without credentials.

## Validation

```bash
npm run build
cd backend && .venv/bin/python -m pytest tests -q
```

The backend tests include regression coverage for Big Buck Bunny and Sprite Fright semantic accessibility presentation, sliding-window behavior, durable movie memory, and timestamped temporal-fact persistence. The frontend build type-checks the viewer and produces a Vite production bundle.

## Deployment Notes

1. Deploy `backend/` with its `render.yaml` or `Dockerfile`.
2. Configure server-side secrets, including `OPENAI_API_KEY` and optionally `OPENAI_MODEL`.
3. Use persistent shared storage or a database-backed knowledge/memory store before running multiple backend instances.
4. Deploy the Vite frontend and set `VITE_MAGIFAB_BACKEND_URL` to the backend’s public origin.
5. Restrict backend CORS to the deployed frontend origin in production.

Movie assets are configured in `src/config/movies.ts`. Production ingestion should preserve stable movie IDs, scene IDs, timestamps, representative frames, and knowledge revisions.

## Future Improvements

MagiFab’s architecture is designed to support deeper temporal intelligence:

- **Adaptive companions:** adjust language, pacing, prompts, and visual presentation to an individual viewer’s accessibility profile.
- **Cross-scene reasoning:** create richer causal links, callbacks, and long-range relationship explanations across scene boundaries.
- **Streaming inference:** process live playback with incremental scheduling and adaptive sampling rather than fixed preparation points.
- **Long-form movie memory:** move durable StoryState snapshots and StoryEvents to a scalable database and add retrieval strategies for feature-length films and series.
- **Temporal attention:** prioritize events and memory retrieval based on narrative salience, recency, uncertainty, and viewer needs.
- **Emotion prediction:** combine expression, action, dialogue, music, and story context to reason about evolving emotional arcs with calibrated uncertainty.
- **Personalized accessibility:** learn which explanations, diagrams, reminders, and prompt types most effectively support a particular viewer.
- **Online learning:** incorporate reviewed feedback and corrections into knowledge quality workflows without allowing unverified model output to become durable fact.

MagiFab is ultimately a research direction: accessibility support that understands not only what a movie shows, but how its meaning unfolds over time.
