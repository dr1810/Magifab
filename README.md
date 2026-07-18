# MagiFab

MagiFab is an accessibility companion for movie watching. It uses structured movie knowledge and a personalized companion to explain scenes, characters, relationships, emotions, timelines, and vocabulary in clear language.

## Architecture

```text
React movie viewer
  ├─ captures a frame only after a user selects a prompt
  ├─ cancels requests during seeking or when a bubble closes
  └─ renders returned bubbles, drawer cards, and accessibility aids
                  │
                  ▼
FastAPI companion pipeline: POST /api/v1/companion/respond
  ├─ retrieval-first Semantic Movie Knowledge lookup
  ├─ scene miss only: YOLO + Florence + optional Grounding DINO + optional face verification
  ├─ Perception Fusion → Semantic Matching → versioned knowledge expansion
  ├─ deterministic accessibility reasoning
  └─ GPT-5.6 wording behind revision-aware response caching
```

The frontend does not identify characters, analyze frames, infer relationships, or generate accessibility reasoning. It sends the current frame, timestamp, prompt, and onboarding profile only when the user asks for help.

## Screenshots

| View | Placeholder |
| --- | --- |
| Movie player and contextual water bubble | Add `docs/screenshots/movie-player-bubble.png` |
| Visual drawer with backend character, relationship, timeline, emotion, memory, and vocabulary content | Add `docs/screenshots/visual-drawer.png` |

## Local setup

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

Create `.env.local` in the project root:

```bash
VITE_MAGIFAB_BACKEND_URL=http://127.0.0.1:8000
```

Then run:

```bash
npm install
npm run dev
```

Open the URL printed by Vite. The browser must be able to reach the configured backend URL. The OpenAI key belongs only in the backend environment—never in `.env.local` or frontend code.

## Deployment

1. Deploy `backend/` using its `render.yaml` or `Dockerfile`.
2. Configure backend secrets: `OPENAI_API_KEY` and, optionally, `OPENAI_MODEL`.
3. Attach persistent storage or replace the development file knowledge store with Postgres/Supabase before scaling beyond one instance.
4. Deploy the Vite frontend to a static host and set `VITE_MAGIFAB_BACKEND_URL` to the public backend URL.
5. Set the backend CORS origins to the frontend deployment origin rather than `*` for production.

Movie video assets are configured in [src/config/movies.ts](/Users/rameshlathimuthu/Desktop/Magifab/src/config/movies.ts). New movie IDs are supported by the backend’s retrieval-first knowledge store; production ingestion should supply stable IDs, timestamps, and representative frames.

## Validation

```bash
npm run build
cd backend && .venv/bin/python -m compileall -q . -x 'venv'
```

The backend contract has tests for retrieval, scene expansion, model-fusion evidence, response caching, health, and OpenAPI discovery. The frontend build checks TypeScript and produces a Vite production bundle.

## Future improvements

- Authenticated movie upload, transcoding, scene detection, and transcript extraction.
- Persistent multi-instance knowledge and response caching.
- Background preprocessing with human verification for characters and relationships.
- Model queues, rate limiting, observability, and privacy-retention controls.
- Captured screenshots and accessibility regression tests for player, prompt, and drawer interactions.
