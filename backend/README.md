# MagiFab semantic scene backend

## Overview

This is the modular backend foundation for MagiFab. It is deliberately **model-free in Phase 1**: it exposes a stable FastAPI service, but performs no perception, matching, caching, or GPT reasoning.

```text
Movie frame → [Phase 2: YOLO] → [Phase 3: Florence] → [later semantic layers]
```

## Status

- Completed: Phase 1 — FastAPI foundation, configuration, structured errors, CORS, Swagger, Docker and Render configuration.
- Pending: Phase 2 object detection; Phase 3 scene understanding; Phase 4 semantic matching; Phase 5 knowledge; Phase 6 GPT personalization; Phase 7 face verification; Phase 8 Grounding DINO.

## Structure

```text
backend/
  app.py                 # Application factory and middleware
  config.py              # Environment configuration
  routers/health.py      # Root and health routes
  schemas/health.py      # Pydantic response models
  models/                # Future model-agnostic contracts
  services/              # Future business services
  utils/                 # Future shared helpers
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

Open [Swagger](http://127.0.0.1:8000/docs). The available endpoints are `GET /` and `GET /health`.

## Configuration

Settings use the `MAGIFAB_` prefix: `MAGIFAB_ENVIRONMENT`, `MAGIFAB_LOG_LEVEL`, and `MAGIFAB_CORS_ORIGINS`. Comma-separate CORS origins in production.

## Deployment

`render.yaml` is a Render Blueprint configured with `/health` as its health check. Docker deployments can build from `backend/Dockerfile`.

## Current limitations

There are intentionally no model endpoints or dependencies in this phase. The frontend is not integrated. Phase 2 will add only object detection behind a replaceable interface.
