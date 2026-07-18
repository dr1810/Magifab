# MagiFab semantic scene backend

## Overview

This is the modular backend for MagiFab. Phase 5 conservatively compares fused perception evidence with caller-supplied movie knowledge; it never invents a match, uses GPT, or integrates with the frontend.

```text
Movie frame → YOLOv11n + Florence-2 Base → Perception Fusion → Semantic Matching → [later knowledge layers]
```

## Status

- Completed: Phase 1 — FastAPI foundation, configuration, structured errors, CORS, Swagger, Docker and Render configuration.
- Completed: Phase 2 — modular YOLOv11n object detection with lazy loading.
- Completed: Phase 3 — modular Florence-2 Base scene understanding with lazy loading.
- Completed: Phase 4 — model-independent perception fusion and unified scene representation.
- Completed: Phase 5 — conservative semantic matching against structured movie knowledge.
- Pending: persistent semantic movie knowledge; GPT personalization; face verification; Grounding DINO.

## Structure

```text
backend/
  app.py                 # Application factory and middleware
  config.py              # Environment configuration
  adapters/yolo_adapter.py       # YOLO-specific implementation
  adapters/florence_adapter.py   # Florence-2-specific implementation
  adapters/perception_evidence.py # Output normalization adapters
  models/object_detector.py      # Replaceable ObjectDetector contract
  models/vision_language_model.py # Replaceable VisionLanguageModel contract
  models/perception_evidence_adapter.py # Future perception-provider contract
  models/semantic_matcher.py      # Replaceable SemanticMatcher contract
  routers/detect.py              # POST /api/v1/detect
  routers/understand.py          # POST /api/v1/understand
  routers/fusion.py              # POST /api/v1/fuse
  routers/match.py               # POST /api/v1/match
  services/object_detection.py   # Model-independent service
  services/vision_understanding.py # Model-independent service
  services/perception_fusion.py  # Evidence fusion service
  services/semantic_matching.py  # Conservative semantic matcher
  schemas/detection.py           # Detection HTTP schemas
  schemas/understanding.py       # Scene-understanding HTTP schemas
  schemas/fusion.py              # Unified-scene and fusion HTTP schemas
  schemas/knowledge.py           # Structured semantic movie knowledge schema
  schemas/matching.py            # Semantic-match request and result schemas
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

Open [Swagger](http://127.0.0.1:8000/docs). The available endpoints are `GET /`, `GET /health`, `POST /api/v1/detect`, `POST /api/v1/understand`, `POST /api/v1/fuse`, and `POST /api/v1/match`.

## Configuration

Settings use the `MAGIFAB_` prefix. Phase 2 adds `MAGIFAB_YOLO_MODEL_ID`, `MAGIFAB_YOLO_DEVICE` (`auto`, `mps`, or `cpu`), and `MAGIFAB_DETECTION_CONFIDENCE_THRESHOLD`. Phase 3 adds `MAGIFAB_FLORENCE_MODEL_ID`, `MAGIFAB_FLORENCE_DEVICE`, and `MAGIFAB_FLORENCE_MAX_NEW_TOKENS`. Model identifiers are configured centrally; business services never name a model.

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
