# MagiFab semantic scene backend

## Overview

This is the modular backend for MagiFab. Phase 10 adds conservative face verification using RetinaFace detection and ArcFace embeddings. Semantic Movie Knowledge remains the only authority for character identities; the frontend is not integrated.

```text
Movie frame → YOLO / Florence / RetinaFace + ArcFace → Semantic Knowledge → Accessibility Reasoning → GPT-5.6 language personalization
```

## Status

- Completed: Phase 1 — FastAPI foundation, configuration, structured errors, CORS, Swagger, Docker and Render configuration.
- Completed: Phase 2 — modular YOLOv11n object detection with lazy loading.
- Completed: Phase 3 — modular Florence-2 Base scene understanding with lazy loading.
- Completed: Phase 4 — model-independent perception fusion and unified scene representation.
- Completed: Phase 5 — conservative semantic matching against structured movie knowledge.
- Completed: Phase 6 — versioned Semantic Movie Knowledge storage, graph lookup, and retrieval-first access.
- Completed: Phase 7 — retrieval-first knowledge expansion, observation merge, and cache-versioned results.
- Completed: Phase 8 — deterministic, profile-adapted accessibility reasoning.
- Completed: Phase 9 — GPT-5.6 language-only personalization over structured facts.
- Completed: Phase 10 — lazy face detection, embedding generation, and conservative identity verification.
- Pending: Grounding DINO.

## Structure

```text
backend/
  app.py                 # Application factory and middleware
  config.py              # Environment configuration
  adapters/yolo_adapter.py       # YOLO-specific implementation
  adapters/florence_adapter.py   # Florence-2-specific implementation
  adapters/perception_evidence.py # Output normalization adapters
  adapters/retinaface_arcface_adapter.py # InsightFace-specific face perception
  models/object_detector.py      # Replaceable ObjectDetector contract
  models/vision_language_model.py # Replaceable VisionLanguageModel contract
  models/perception_evidence_adapter.py # Future perception-provider contract
  models/semantic_matcher.py      # Replaceable SemanticMatcher contract
  models/knowledge_store.py       # Replaceable knowledge persistence contract
  models/accessibility_reasoner.py # Replaceable accessibility-reasoning contract
  models/language_personalizer.py # Replaceable language-personalization contract
  models/face_embedding_extractor.py # Replaceable face detection/embedding contract
  routers/detect.py              # POST /api/v1/detect
  routers/understand.py          # POST /api/v1/understand
  routers/fusion.py              # POST /api/v1/fuse
  routers/match.py               # POST /api/v1/match
  routers/knowledge.py           # Versioned knowledge storage/retrieval endpoints
  routers/knowledge_expansion.py # POST /api/v1/knowledge/expand
  routers/accessibility_reasoning.py # POST /api/v1/accessibility/reason
  routers/personalization.py     # POST /api/v1/personalize
  routers/face_verification.py   # POST /api/v1/face-verification
  services/object_detection.py   # Model-independent service
  services/vision_understanding.py # Model-independent service
  services/perception_fusion.py  # Evidence fusion service
  services/semantic_matching.py  # Conservative semantic matcher
  services/knowledge_store.py    # Atomic JSON knowledge persistence
  services/knowledge_retriever.py # Retrieval-first service
  services/movie_knowledge_graph.py # Scene/timeline graph traversal
  services/knowledge_expansion.py # Retrieval-first perception-to-knowledge engine
  services/accessibility_reasoning.py # Deterministic accessibility content engine
  services/gpt_personalization.py # Language-only personalization service
  services/face_verification.py  # Knowledge-reference face verification service
  schemas/detection.py           # Detection HTTP schemas
  schemas/understanding.py       # Scene-understanding HTTP schemas
  schemas/fusion.py              # Unified-scene and fusion HTTP schemas
  schemas/knowledge.py           # Structured semantic movie knowledge schema
  schemas/matching.py            # Semantic-match request and result schemas
  schemas/knowledge.py           # Versioned movie-knowledge record schemas
  schemas/knowledge_expansion.py # Expansion request/result schemas
  schemas/accessibility_reasoning.py # Accessibility request/result schemas
  schemas/personalization.py     # GPT personalization request/result schemas
  schemas/face_verification.py   # Face-verification request/result schemas
  utils/image.py                 # Safe base64 image decoder
  cache/                 # Runtime cache mount point
  Dockerfile
  render.yaml
```

## Local setup

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Open [Swagger](http://127.0.0.1:8000/docs). The available endpoints include `GET /`, `GET /health`, the perception/matching endpoints, `POST /api/v1/face-verification`, and knowledge retrieval routes under `/api/v1/knowledge`.

## Configuration

Settings use the `MAGIFAB_` prefix. Phase 2 adds `MAGIFAB_YOLO_MODEL_ID`, `MAGIFAB_YOLO_DEVICE` (`auto`, `mps`, or `cpu`), and `MAGIFAB_DETECTION_CONFIDENCE_THRESHOLD`. Phase 3 adds `MAGIFAB_FLORENCE_MODEL_ID`, `MAGIFAB_FLORENCE_DEVICE`, and `MAGIFAB_FLORENCE_MAX_NEW_TOKENS`. Phase 10 adds `MAGIFAB_FACE_MODEL_PACK` (default `buffalo_l`), `MAGIFAB_FACE_ONNX_PROVIDERS` (default CPU), `MAGIFAB_FACE_DETECTION_SIZE`, and `MAGIFAB_FACE_VERIFICATION_THRESHOLD`. Model identifiers are configured centrally; business services never name a model.

## Deployment

`render.yaml` is a Render Blueprint configured with `/health` as its health check. Docker deployments can build from `backend/Dockerfile`.

## Current limitations

`POST /api/v1/detect` accepts `{ "image": "<base64 or data URL>" }` and returns ordinary object labels, confidence scores, and pixel-space `[x, y, width, height]` boxes.

`POST /api/v1/understand` accepts the same image input and returns `scene_description`, `detected_actions`, `environment`, `important_objects`, and `interactions`. Florence weights download only on the first valid request. The adapter exposes only caption-backed perception fields and never assigns a movie-character identity or semantic relationship. There is no semantic matching, GPT integration, or frontend wiring.

## Phase 4: Perception Fusion

`POST /api/v1/fuse` accepts existing YOLO and Florence response objects and performs **no image inference**. It returns a `UnifiedSceneRepresentation` containing:

- `entities`, plus filtered `people`, `animals`, and `objects`
- pixel bounding boxes and confidence values when provided by a detector
- `environment`, `actions`, `interactions`, and provider-backed `visual_attributes`
- a `providers` list for provenance

The fusion service consumes generic `PerceptionContribution` values. `PerceptionEvidenceAdapter` is the extension point for Grounding DINO, face verification, or other future perception providers. These providers can contribute evidence without changing the unified response schema or downstream services. The layer categorizes generic labels only; it never identifies a movie character, maps relationships, or performs semantic reasoning.

## Phase 5: Semantic Matching

`POST /api/v1/match` accepts a `UnifiedSceneRepresentation` plus a structured `SemanticMovieKnowledge` slice. It returns only knowledge facts that have exact, unambiguous visual evidence above `MAGIFAB_SEMANTIC_MATCH_CONFIDENCE_THRESHOLD` (default `0.8`): characters, locations, objects, relationships, events, and linked timeline positions.

Character matching uses only a knowledge character's explicit `perception_labels`, never a language-model guess. If labels are ambiguous, unseen, or below threshold, `character_found` is `false` and no character is returned. Relationships require both referenced characters to have already been verified. Events require every configured evidence term to be observed. This endpoint persists nothing and does not call GPT.

## Phase 6: Semantic Movie Knowledge

`SemanticMovieKnowledge` is a versioned structured representation for movie facts: characters, objects, relationships, locations, timeline positions, events, dialogue, scene summaries, known aliases, visual anchors, observation history, and confidence values.

`KnowledgeStore` is the persistence contract. The default `FileKnowledgeStore` writes atomic JSON revisions below `cache/movie-knowledge/`, using a SHA-256 movie-ID filename so external IDs cannot alter file paths. It can be replaced with Supabase, Postgres, or another store without changing `KnowledgeRetriever`.

`MovieKnowledgeGraph` resolves a scene by ID or timestamp and finds a timeline position. `KnowledgeRetriever` is retrieval-first: it returns `{ "found": false }` for a miss and does not perform model inference, semantic enrichment, or GPT fallback.

- `PUT /api/v1/knowledge/{movie_id}` creates or updates a record and increments its revision.
- `GET /api/v1/knowledge/{movie_id}` reads the latest record.
- `POST /api/v1/knowledge/retrieve` returns the record plus an optional scene and timeline slice.

## Phase 7: Knowledge Expansion

`POST /api/v1/knowledge/expand` is the retrieval-first orchestration endpoint. Its input contains `movie_id`, `timestamp_seconds`, optional `scene_id`, and an image only for a potential miss.

1. If the movie record exists, it is retrieved immediately. The image is not decoded, and YOLO, Florence, fusion, and GPT are not invoked.
2. If no record exists, the engine decodes the image and runs the existing object-detection, scene-understanding, and perception-fusion services.
3. It merges only observed entity labels, anchors, scene summary, environment, aliases, confidence, and observation-history items into a new `SemanticMovieKnowledge` record.
4. The `FileKnowledgeStore` persists the next revision and the result returns a versioned cache key such as `movie-id:v1:scene-id`.

The expansion engine never creates character identities, relationships, events, or dialogue from perception. `merge_observations` is exposed as a pure structured merge operation for future verified-update workflows; the endpoint's normal policy deliberately avoids reprocessing an existing record.

## Phase 8: Accessibility Reasoning

`POST /api/v1/accessibility/reason` accepts Semantic Movie Knowledge, the current scene and timestamp, an Accessibility Profile, and a Companion Profile. It returns structured JSON only:

- Likely confusion predictions and contextual prompt bubbles
- Accessibility drawer content: character cards, relationship and timeline summaries, verified emotion summaries, memory reminders, vocabulary help, and current-dialogue simplifications
- Suggested follow-up questions and a companion tone descriptor

The engine adapts output through onboarding selections: `accessibility_needs` decide which cards, summaries, prompts, reminders, and simplifications appear; `detail_level` controls the number of items; preferred prompt types filter suggestions; vocabulary and conversation toggles control their corresponding sections. It uses only explicit stored facts. Missing emotion, dialogue, relationship, or vocabulary facts produce empty structured sections rather than invented content. No GPT, image inference, semantic matching, cache mutation, or frontend change occurs in this phase.

## Phase 9: GPT-5.6 Personalization

`POST /api/v1/personalize` accepts a user message plus structured Semantic Movie Knowledge, the current scene, deterministic accessibility content, and onboarding-derived accessibility/companion profiles. It sends this JSON to GPT-5.6 through the server-side Responses API and returns a structured `{ "response", "model" }` object.

The adapter instruction explicitly limits GPT to wording: accessible explanations, simplified language, personalized phrasing, and natural conversation. It forbids character identification, object detection, visual inspection, semantic matching, relationship/emotion inference, and redoing backend reasoning. Facts absent from the request must be treated as unknown.

Set `OPENAI_API_KEY` only in the backend environment; it is never a browser variable or API response. `OPENAI_MODEL` is optional and defaults to `gpt-5.6`. The service is lazy: it does not create an OpenAI client until `/api/v1/personalize` is called. A missing key returns HTTP 503; an upstream provider failure returns HTTP 502.

## Phase 10: Face Verification

`POST /api/v1/face-verification` accepts a base64 image and Semantic Movie Knowledge. On its first request, the replaceable `FaceEmbeddingExtractor` implementation lazily loads an InsightFace model pack containing RetinaFace detection and ArcFace recognition models. It detects faces and generates normalized embeddings locally. Raw embeddings are intentionally not returned by the HTTP API.

Verification compares each generated embedding only with `face_references` enrolled in the supplied Semantic Movie Knowledge. A reference is usable only if its `character_id` exists in the knowledge's `characters` list. The endpoint returns `verified: true` and `verified_character_id` only when exactly one enrolled character passes the configured similarity threshold. Multiple candidates, no candidate, dimension mismatches, and unknown references all return `verified: false`; the service never creates, guesses, or directly assigns a character identity.

Face analysis is an independent perception component. It does not alter movie knowledge, invoke GPT, perform semantic matching, or communicate with the frontend. A different detector/embedding implementation can replace `RetinaFaceArcFaceAdapter` without changing the service or endpoint contract. Review the selected pretrained model's license before production deployment; InsightFace documents that model-pack weights can have separate usage terms.
