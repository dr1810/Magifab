# MagiFab Semantic Movie Backend

## Overview

This FastAPI backend is the server-only runtime for MagiFab’s movie accessibility companion. A movie is now ingested once, understood in durable 90-second scene records, and then served to the companion without the browser calling Gemini or OpenAI.

```text
Movie upload (content hash)
        │
        ▼
Hash cache hit ───────────────────────────────────────────────► stored scenes
        │ cache miss
        ▼
FFmpeg approximately-90-second MP4 chunks
        │
        ▼
Gemini Video API (visual evidence only)
        │
        ▼
Selective Google Search grounding for unresolved entities
        │
        ▼
OpenAI evidence-bounded reasoning
        │
        ▼
Canonical MagiFab scene JSON → durable scene/search/chunk records → companion API
```

`/api/v1/companion/*` remains available for the legacy prepared-interval runtime during migration. New uploaded movies must use `/api/v1/movies/*`; it never decodes client frames or exposes provider credentials.

## Movie preprocessing API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/movies/upload` | Multipart `video` upload with optional `title`; identical SHA-256 content returns the existing movie ID. |
| POST | `/api/v1/movies/{movie_id}/preprocess` | Start background preprocessing, or immediately report an existing completed/active job. |
| GET | `/api/v1/movies/{movie_id}` | Read the persistent movie metadata and processing state. |
| GET | `/api/v1/movies/{movie_id}/processing-status` | Read movie and per-chunk statuses. |
| GET | `/api/v1/movies/{movie_id}/scene?timestamp=…` | Read exactly the persisted scene/chunk active at playback time; it cannot invoke AI. |
| GET | `/api/v1/movies/{movie_id}/video` | Development-only source-video streaming; production should issue an authorised private-storage URL. |
| GET | `/api/v1/movies/{movie_id}/chunks` | Read durable chunk metadata and Gemini visual JSON. |
| GET | `/api/v1/movies/{movie_id}/scenes` | Read canonical, frontend-facing scenes only. |

The source blob, chunk blob, SHA-256 hashes, created times, model versions, raw Gemini visual JSON, Google Search context, canonical scene JSON, and attempt history are persisted separately. The local implementation is SQLite plus filesystem blobs under `cache/movie-pipeline`; the repository and blob interfaces map directly to the supplied Supabase migration.

Gemini gets the entire chunk as a video file. It is constrained to visual observations and uses `Unknown` / `low` confidence for uncertainty. Google Search is invoked only for explicit `entities_needing_identification` of an approved type (unknown character, creature, landmark, movie title, object text, organization, book, or historical person), never generic scenery. OpenAI receives only that visual JSON and cited search evidence, and its prompt requires unsupported identities to remain `Unknown`.

## Frontend playback integration

The frontend keeps its existing player, water-bubble prompt UI, companion, visual drawer, onboarding, and accessibility controls. `MoviePreprocessingBackendService` is the only browser API client: it uploads/starts a movie, polls its status, caches metadata/timeline/scene responses, retrieves the active scene from `video.currentTime`, and preloads adjacent chunks. `StoredSceneState` adapts the canonical scene document into the established `SceneState` used by prompt bubbles, the drawer, and the local deterministic companion responder. No provider call or legacy companion-generation endpoint is made during playback.

## Retrieval and caching

`POST /api/v1/companion/intervals/prepare` is the preparation endpoint. It is the only companion endpoint permitted to run perception for an unknown scene. `POST /api/v1/companion/respond` is retrieval-only: it reads a prepared scene and never decodes an image, runs a perception model, or calls GPT.

## Preparation-first runtime

```
Representative scene frame → YOLO / Florence / optional grounding → Perception Fusion
→ Semantic Matching → Semantic Movie Knowledge (visible entities, anchors, actions)
→ deterministic prompt bubbles and drawer
```

Each `SceneSummary` is marked `prepared` only after the perception record has been persisted. Prompt bubbles are derived from its `visible_entities`; unnamed animals or people can be described generically, but cannot be promoted to movie characters. Title/loading frames are not prepared by the frontend until playback has advanced beyond its initial buffer.

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

## Migrating uploaded movies

1. Install the updated requirements, including `google-genai` and `python-multipart`.
2. Apply `supabase/migrations/20260721110000_movie_preprocessing_pipeline.sql` and implement a production `MoviePipelineRepository` / `MovieBlobStorage` backed by Supabase Postgres and Storage. The included SQLite implementation is for local development.
3. Put source videos and chunks in private object storage; do not return their paths or provider keys to the browser.
4. Change the frontend upload flow to `POST /api/v1/movies/upload`, then start/poll preprocessing and consume `GET /scene?timestamp=…` from the player. Remove any client-side frame preparation for newly uploaded movies.
5. Existing legacy interval records can remain readable while movies are re-ingested. Do not migrate their unverified frame-level inference into canonical scenes; process the original movie to obtain continuous video evidence.

The React client exposes this boundary through `src/services/backend/MoviePreprocessingBackendService.ts`; it uses only these backend endpoints and contains no Gemini, Google Search, or OpenAI SDK call.

## Local development

```bash
cd backend
brew install python@3.11
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
export OPENAI_API_KEY="server-side-only-key"
export OPENAI_MODEL="gpt-5.6" # optional
export GEMINI_API_KEY="server-side-only-key"
export GEMINI_MODEL="gemini-2.5-flash" # optional
MPLCONFIGDIR=/tmp/magifab-mpl uvicorn app:app --host 127.0.0.1 --port 8000
```

This runtime is pinned for Apple Silicon, macOS, MPS, and Python 3.11. Startup preloads YOLO, Florence-2, and Grounding DINO sequentially; use a single Uvicorn worker so one `ModelManager` owns exactly one instance of every model. The OpenAI key is read only by the server and is never browser-facing.

### Runtime verification

Run the model checks independently before diagnosing the full server:

```bash
MPLCONFIGDIR=/tmp/magifab-mpl python scripts/verify_yolo.py
MPLCONFIGDIR=/tmp/magifab-mpl python scripts/verify_florence.py
MPLCONFIGDIR=/tmp/magifab-mpl python scripts/verify_grounding_dino.py
curl http://127.0.0.1:8000/health
open http://127.0.0.1:8000/docs
```

Startup logs report Python, Torch, MPS availability, elapsed time, RSS, and MPS allocation before and after every model. On Apple Silicon, `torch.backends.mps.is_available()` must be `True` and each model should report `device=mps`.

### Model caches and troubleshooting

Hugging Face stores model artifacts under `~/.cache/huggingface/hub`; Ultralytics stores settings and downloaded weights under `~/Library/Application Support/Ultralytics` and its configured weights directory. A partially downloaded or incompatible cache must be removed explicitly before retrying:

```bash
rm -rf ~/.cache/huggingface/hub/models--microsoft--Florence-2-base
rm -rf ~/.cache/huggingface/hub/models--IDEA-Research--grounding-dino-tiny
```

If Ultralytics reports a checkpoint/module compatibility error such as a missing `Conv.bn`, reinstall the pinned requirements and replace the local `yolo11n.pt` with the checkpoint downloaded by that pinned Ultralytics release. Do not mix an existing Python 3.13 virtual environment or Transformers 5.x cache with this Python 3.11 runtime.

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

For Render, configure `OPENAI_API_KEY` and `GEMINI_API_KEY` as secrets, set either model variable only when overriding defaults, and attach persistent storage for local development. Production deployments should use the supplied Postgres schema plus private object storage, a durable job queue, rate limits, and a shared cache.

## Limitations

- File-backed knowledge and in-memory response caching are process-local; they are appropriate for development, not multi-instance durability.
- The local upload implementation uses FastAPI background tasks and SQLite. It is durable across restarts but is not a distributed work queue; production should use a worker queue with leases.
- FFmpeg and ffprobe must be installed on the preprocessing worker.
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
