# MagiFab semantic scene backend

## Overview

This is the modular perception backend for MagiFab. Phase 3 performs object detection and Florence-2 scene perception only; it does not identify movie characters, perform semantic matching, use GPT, or integrate with the frontend.

```text
Movie frame → YOLOv11n object detection + Florence-2 Base scene understanding → [later semantic layers]
```

## Status

- Completed: Phase 1 — FastAPI foundation, configuration, structured errors, CORS, Swagger, Docker and Render configuration.
- Completed: Phase 2 — modular YOLOv11n object detection with lazy loading.
- Completed: Phase 3 — modular Florence-2 Base scene understanding with lazy loading.
- Pending: Phase 4 semantic matching; Phase 5 knowledge; Phase 6 GPT personalization; Phase 7 face verification; Phase 8 Grounding DINO.

## Structure

```text
backend/
  app.py                 # Application factory and middleware
  config.py              # Environment configuration
  adapters/yolo_adapter.py       # YOLO-specific implementation
  adapters/florence_adapter.py   # Florence-2-specific implementation
  models/object_detector.py      # Replaceable ObjectDetector contract
  models/vision_language_model.py # Replaceable VisionLanguageModel contract
  routers/detect.py              # POST /api/v1/detect
  routers/understand.py          # POST /api/v1/understand
  services/object_detection.py   # Model-independent service
  services/vision_understanding.py # Model-independent service
  schemas/detection.py           # Detection HTTP schemas
  schemas/understanding.py       # Scene-understanding HTTP schemas
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

Open [Swagger](http://127.0.0.1:8000/docs). The available endpoints are `GET /`, `GET /health`, `POST /api/v1/detect`, and `POST /api/v1/understand`.

## Configuration

Settings use the `MAGIFAB_` prefix. Phase 2 adds `MAGIFAB_YOLO_MODEL_ID`, `MAGIFAB_YOLO_DEVICE` (`auto`, `mps`, or `cpu`), and `MAGIFAB_DETECTION_CONFIDENCE_THRESHOLD`. Phase 3 adds `MAGIFAB_FLORENCE_MODEL_ID`, `MAGIFAB_FLORENCE_DEVICE`, and `MAGIFAB_FLORENCE_MAX_NEW_TOKENS`. Model identifiers are configured centrally; business services never name a model.

## Deployment

`render.yaml` is a Render Blueprint configured with `/health` as its health check. Docker deployments can build from `backend/Dockerfile`.

## Current limitations

`POST /api/v1/detect` accepts `{ "image": "<base64 or data URL>" }` and returns ordinary object labels, confidence scores, and pixel-space `[x, y, width, height]` boxes.

`POST /api/v1/understand` accepts the same image input and returns `scene_description`, `detected_actions`, `environment`, `important_objects`, and `interactions`. Florence weights download only on the first valid request. The adapter exposes only caption-backed perception fields and never assigns a movie-character identity or semantic relationship. There is no semantic matching, GPT integration, or frontend wiring.
