# MagiFab Semantic Movie Backend

## Overview

This FastAPI backend is the modular runtime for MagiFab’s movie accessibility companion. It separates visual perception, verified movie knowledge, deterministic accessibility reasoning, and GPT-5.6 language personalization. The React application is intentionally not coupled to this service.

```text
Movie frame + request
        │
        ▼
Scene-level Semantic Movie Knowledge retrieval
        │
        ├─ known scene ────────────────► Accessibility Reasoning ─► Versioned response cache ─► GPT-5.6 wording
        │
        └─ scene miss
             │
             ▼
  YOLO + Florence + optional Grounding DINO + optional face verification
             │
             ▼
      Perception Fusion Layer
             │
             ▼
      Semantic Matching Engine
             │
             ▼
      Semantic Movie Knowledge expansion and versioned persistence
             │
             └────────────────────────► Accessibility Reasoning ─► GPT-5.6 wording
```

## Retrieval and caching

`POST /api/v1/companion/respond` is the integrated runtime endpoint.

1. It retrieves the requested movie scene before decoding an image or loading a model.
2. A known scene bypasses all perception models.
3. A movie or scene miss requires an image. The expansion engine runs YOLO and Florence, and runs Grounding DINO or face verification only when requested.
4. All available perception evidence is normalized by the Perception Fusion Layer, then matched conservatively against Semantic Movie Knowledge.
5. Observed facts are saved as a new atomic knowledge revision.
6. Accessibility content is deterministic and profile-aware.
7. GPT receives only the verified structured facts and accessibility content. Its text response is cached by movie, knowledge revision, scene, timestamp bucket, intent, question, grounding request, and onboarding profiles.

The in-memory response cache is LRU-bounded and uses a single-flight mechanism, so simultaneous identical requests share one GPT request. A new knowledge revision changes the cache key, making prior wording unreachable without unsafe manual invalidation.

## Models

| Component | Default implementation | Responsibility |
| --- | --- | --- |
| Object detection | YOLOv11n | Generic object labels, confidence, and boxes; never names characters. |
| Scene understanding | Florence-2 Base | Captions, actions, environment, objects, and interactions; never names characters. |
| Object grounding | Grounding DINO Tiny | On-demand text-guided boxes for phrases such as `squirrel` or `flower`. |
| Face perception | RetinaFace + ArcFace via InsightFace | Face boxes and embeddings; verifies only enrolled Semantic Movie Knowledge references. |
| Semantic matching | Deterministic service | Exact, unambiguous matches against stored knowledge only. |
| Language | GPT-5.6 | Accessible wording and personalization only; no visual perception or fact invention. |

Every model-specific dependency is isolated behind an adapter contract. Replace an adapter without changing API schemas or business services.

## API reference

Swagger is available at `http://127.0.0.1:8000/docs` when running locally.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/` | Service metadata |
| GET | `/health` | Health check |
| POST | `/api/v1/detect` | YOLO object detection |
| POST | `/api/v1/understand` | Florence scene understanding |
| POST | `/api/v1/ground` | Grounding DINO requested-object localization |
| POST | `/api/v1/face-verification` | Face embedding generation and enrolled-reference verification |
| POST | `/api/v1/fuse` | Fuse supplied perception results without inference |
| POST | `/api/v1/match` | Match fused evidence against semantic knowledge |
| PUT/GET | `/api/v1/knowledge/{movie_id}` | Store or retrieve versioned Semantic Movie Knowledge |
| POST | `/api/v1/knowledge/retrieve` | Retrieve a movie, scene, and timeline slice |
| POST | `/api/v1/knowledge/expand` | Retrieval-first scene expansion from a frame |
| POST | `/api/v1/accessibility/reason` | Deterministic accessibility content |
| POST | `/api/v1/personalize` | GPT wording over verified facts |
| POST | `/api/v1/companion/respond` | Full retrieval-first runtime pipeline |

### Integrated request

`POST /api/v1/companion/respond` accepts a `movie_id`, timestamp, optional `scene_id`, user-facing scene summary, question, intent, onboarding-derived accessibility and companion profiles, and an image only for a missing scene. `grounding_queries` and `verify_faces` opt into their respective on-demand perception stages.

```json
{
  "movie_id": "uploaded-movie-123",
  "timestamp_seconds": 42,
  "scene_id": "scene-004",
  "scene_summary": "A squirrel is near a flower.",
  "question": "Where is the flower?",
  "intent": "object_location",
  "image": "base64 image required only for a scene miss",
  "grounding_queries": ["flower"],
  "verify_faces": false,
  "accessibility_profile": {
    "accessibility_needs": ["remember_characters"],
    "detail_level": "brief"
  },
  "companion_profile": {
    "name": "Magi",
    "personality": "patient",
    "conversation_style": "simple"
  }
}
```

The response includes cache metadata, the personalized response, deterministic accessibility content, and—only on a scene miss—the fused perception and conservative semantic matches.

## Future uploaded movies

Movie IDs are opaque and are not restricted to bundled content. A newly uploaded movie can send its first representative frame to `/api/v1/knowledge/expand` or `/api/v1/companion/respond`; the backend creates an isolated, hashed knowledge record under `cache/movie-knowledge`. A production deployment should replace `FileKnowledgeStore` with Postgres/Supabase or object-backed storage and connect an authenticated upload/transcoding pipeline that provides stable movie IDs and timestamps.

## Local development

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
export OPENAI_API_KEY="server-side-only-key"
export OPENAI_MODEL="gpt-5.6" # optional
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

The OpenAI key is read only by the server. It is never returned by an endpoint or included in browser-facing configuration. Model weights are downloaded lazily on the first request to each model-backed endpoint.

## Configuration

All general settings use the `MAGIFAB_` prefix. OpenAI also accepts unprefixed `OPENAI_API_KEY` and `OPENAI_MODEL` for common deployment secret conventions.

- `MAGIFAB_YOLO_MODEL_ID`, `MAGIFAB_YOLO_DEVICE`, `MAGIFAB_DETECTION_CONFIDENCE_THRESHOLD`
- `MAGIFAB_FLORENCE_MODEL_ID`, `MAGIFAB_FLORENCE_DEVICE`, `MAGIFAB_FLORENCE_MAX_NEW_TOKENS`
- `MAGIFAB_GROUNDING_DINO_MODEL_ID`, `MAGIFAB_GROUNDING_DINO_DEVICE`, `MAGIFAB_GROUNDING_DINO_BOX_THRESHOLD`, `MAGIFAB_GROUNDING_DINO_TEXT_THRESHOLD`
- `MAGIFAB_FACE_MODEL_PACK`, `MAGIFAB_FACE_ONNX_PROVIDERS`, `MAGIFAB_FACE_DETECTION_SIZE`, `MAGIFAB_FACE_VERIFICATION_THRESHOLD`
- `MAGIFAB_RESPONSE_CACHE_MAX_ENTRIES`, `MAGIFAB_RESPONSE_CACHE_TIMESTAMP_BUCKET_SECONDS`

## Deployment

`render.yaml` deploys the backend with `/health` as its health check. The Docker image is built from `Dockerfile`.

```bash
cd backend
docker build -t magifab-backend .
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY \
  -e OPENAI_MODEL=gpt-5.6 \
  -v "$(pwd)/cache:/app/cache" \
  magifab-backend
```

For Render, configure `OPENAI_API_KEY` as a secret, set `OPENAI_MODEL` if overriding the default, and attach persistent storage for `cache/movie-knowledge` if using the development file store. Production deployments should prewarm or provision model weights, bound concurrent inference, and use a persistent database/cache shared across instances.

## Limitations

- File-backed knowledge and in-memory response caching are process-local; they are appropriate for development, not multi-instance durability.
- The backend accepts already-extracted frames; it does not upload, transcode, preprocess, or continuously analyze video.
- Character identity requires pre-enrolled face references in Semantic Movie Knowledge. Face verification never creates an identity.
- Grounding DINO locates explicit visual phrases; resolving a character name in a phrase remains a verified semantic-knowledge concern.
- Model quality varies with animation style, occlusion, tiny objects, lighting, and motion blur. Empty results are valid and must not be replaced with guesses.
- Review all third-party model-weight licenses before commercial deployment.

## Future roadmap

1. Persistent Postgres/Supabase knowledge, response cache, and multi-worker job coordination.
2. Authenticated uploaded-movie ingestion, scene detection, transcript extraction, and representative-frame preprocessing.
3. Background knowledge enrichment using verified human review and scene-level confidence controls.
4. Object tracking across frames and optional temporal grounding.
5. Production observability, rate limiting, request authorization, model queues, and privacy retention controls.
