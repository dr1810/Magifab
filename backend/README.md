# MagiFab semantic scene backend

## Overview

This is the modular perception backend for MagiFab. Phase 2 performs generic object detection only; it does not identify movie characters, reason about scenes, use GPT, or integrate with the frontend.

```text
Movie frame → YOLOv11n object detection → [Phase 3: Florence] → [later semantic layers]
```

## Status

- Completed: Phase 1 — FastAPI foundation, configuration, structured errors, CORS, Swagger, Docker and Render configuration.
- Completed: Phase 2 — modular YOLOv11n object detection with lazy loading.
- Pending: Phase 3 scene understanding; Phase 4 semantic matching; Phase 5 knowledge; Phase 6 GPT personalization; Phase 7 face verification; Phase 8 Grounding DINO.

## Structure

```text
backend/
  app.py                 # Application factory and middleware
  config.py              # Environment configuration
  adapters/yolo_adapter.py       # YOLO-specific implementation
  models/object_detector.py      # Replaceable ObjectDetector contract
  routers/detect.py              # POST /api/v1/detect
  services/object_detection.py   # Model-independent service
  schemas/detection.py           # Detection HTTP schemas
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

Open [Swagger](http://127.0.0.1:8000/docs). The available endpoints are `GET /`, `GET /health`, and `POST /api/v1/detect`.

## Configuration

Settings use the `MAGIFAB_` prefix. Phase 2 adds `MAGIFAB_YOLO_MODEL_ID`, `MAGIFAB_YOLO_DEVICE` (`auto`, `mps`, or `cpu`), and `MAGIFAB_DETECTION_CONFIDENCE_THRESHOLD`. The default model identifier is configured centrally; business services never name a model.

## Deployment

`render.yaml` is a Render Blueprint configured with `/health` as its health check. Docker deployments can build from `backend/Dockerfile`.

## Current limitations

`POST /api/v1/detect` accepts `{ "image": "<base64 or data URL>" }` and returns ordinary object labels, confidence scores, and pixel-space `[x, y, width, height]` boxes. YOLO weights download only on the first valid request. There is no character identification, semantic reasoning, GPT integration, or frontend wiring.
