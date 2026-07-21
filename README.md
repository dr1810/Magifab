# MagiFab

MagiFab is an accessibility companion for movies and books. It creates durable, personalized story artifacts before a person starts watching or reading. Playback and reading only retrieve those artifacts; they never call Gemini or OpenAI to preprocess content.

## Architecture

### Movie pipeline

```text
Upload movie
  → FFmpeg 90-second chunks
  → Gemini video understanding
  → Google Search evidence for uncertain entities only
  → OpenAI accessibility reasoning (companion profile + accessibility needs)
  → Stored scene artifacts
  → Playback-time retrieval
```

Gemini receives each continuous video chunk, never a frame-analysis pipeline. Google Search is evidence for uncertain, identifiable entities only. The OpenAI reasoning step receives Gemini observations, that evidence, and the user’s companion profile (personality, accessibility needs, difficulties, and explanation style). It generates prompt bubbles, scene explanations, character information, memory cues, Visual Drawer data, and visual aids.

During playback the frontend calls only `GET /api/v1/movies/{movie_id}/scene?timestamp=…` to retrieve the closest stored artifact. Prompt clicks reuse it. Direct questions use the stored-context companion-chat endpoint; neither route triggers preprocessing or Gemini.

### Book pipeline

Books are a separate text pipeline and are never treated as movies.

```text
PDF / EPUB / text upload
  → text extraction per page
  → front-matter filtering (cover, copyright, publisher, TOC)
  → narrative start detection
  → chapter/section/page-range segmentation
  → accessibility reasoning and relationship construction
  → stored chapter artifacts
  → reading-time retrieval
```

The repository includes `books/Frank Herbert - Dune 1 - Dune.pdf`. The backend registers it as the Dune example, and the frontend’s Dune tile starts its book-specific process. Artifacts include chapter summaries, simplified explanations, character cards, directional relationship maps, important events, difficult concepts, memory aids, and chapter-level companion questions.

The book API stores chapter metadata (chapter number/title and page range) and serves a dedicated reading UI layout:

```text
Left panel: cover/progress/chapter list
Center panel: chapter summary + simplified explanation
Right panel: companion chat and quick questions
Bottom tabs: Characters, Relationships, Timeline, Memory Aid, Visual Map
```

## User experience

For movies, an unprocessed upload shows **“Creating your MagiFab companion experience…”** and reports chunking, Gemini analysis, accessibility reasoning, and artifact progress. Once complete, the player uses timestamped prompt bubbles and a Visual Drawer with Characters, Timeline, Objects, Memory, Emotion, and Cause tabs.

For Dune and uploaded books, the loading screen says **“Creating your MagiFab reading companion…”** and reports text extraction, chapter understanding, relationship building, and accessibility explanations. Readers can move through chapters, view the simplified artifact, open relationship information, and ask their companion a stored-context question.

## API

### Movies

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/movies/upload` | Upload a video and return `movie_id`. |
| `POST /api/v1/movies/{movie_id}/preprocess` | Queue the one-time movie pipeline with `companion_profile`. |
| `GET /api/v1/movies/{movie_id}/processing-status` | Returns `queued`, `chunking`, `analyzing`, `reasoning`, `complete`, or `failed`, plus progress and percentage. |
| `GET /api/v1/movies/{movie_id}/scene?timestamp=` | Returns the closest stored scene artifact. |
| `POST /api/v1/movies/{movie_id}/companion/chat` | Answers from stored scene context, companion profile, and question. |
| `GET /api/v1/movies/{movie_id}/video` | Development video streaming endpoint. |

### Books

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/books/upload` | Upload a PDF, EPUB, or text document. |
| `POST /api/v1/books/{book_id}/preprocess` | Queue separate book extraction and accessibility processing. |
| `GET /api/v1/books/{book_id}/processing-status` | Read extraction/reasoning progress. |
| `GET /api/v1/books/{book_id}/chapters` | Retrieve chapter metadata list and page ranges. |
| `GET /api/v1/books/{book_id}/chapter?chapter=` | Retrieve a stored chapter artifact. |
| `POST /api/v1/books/{book_id}/companion/chat` | Answer from the stored chapter context. |

`GET /api/v1/books/examples/dune` resolves the locally supplied Dune example for the frontend tile.

## Local setup

Requirements: Node.js 20+, Python 3.11+, FFmpeg/FFprobe, and Python dependencies from `backend/requirements.txt`.

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/uvicorn app:app --reload --port 8000
```

In another terminal:

```bash
npm install
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`. Optionally set `VITE_MAGIFAB_BACKEND_URL` for a separately deployed backend.

### Environment variables

Set these in `backend/.env`, never in the frontend:

```dotenv
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.6
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
MOVIE_PIPELINE_DIR=cache/movie-pipeline
CORS_ORIGINS=http://localhost:5173
```

The browser has no provider credentials.

## Deployment architecture

The development implementation uses SQLite and local blobs beneath `MOVIE_PIPELINE_DIR`. In production replace those storage adapters with object storage and a durable database, run preprocessing through a job worker, and keep the API deployment stateless. The player and reader should remain retrieval-only clients. Provider keys stay in the backend worker/API environment; never expose them through Vite or the browser.
