# MagiFab API

This is the slim, server-only backend used by the main MagiFab website.

It has two separate content paths:

```text
movie upload → 90-second chunks → Gemini video → Google Search evidence
→ OpenAI canonical scene → stored scene retrieval during playback

book upload / Dune PDF → text extraction → chapter segmentation
→ OpenAI accessibility artifacts → stored chapter retrieval during reading
```

It has no browser-side AI calls or local frame-analysis dependency stack.

## Run locally

FFmpeg and ffprobe are required for chunking:

```bash
brew install ffmpeg
cd backend
python3 -m venv .venv-movie
source .venv-movie/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

The backend depends on the current Gemini SDK package:

```bash
pip install google-genai
```

Use `http://127.0.0.1:8000/docs` to inspect the API. `--reload` is appropriate only while developing.

## Main website configuration

The backend `.env` needs only server-side credentials:

```dotenv
OPENAI_API_KEY=...
GEMINI_API_KEY=...
OPENAI_MODEL=gpt-5.6
GEMINI_MODEL=gemini-2.5-flash
MAGIFAB_CORS_ORIGINS=https://your-main-website.example
```

## Bundled example books

Bundled examples must live inside the backend project so Docker/Render can ship
them with the image:

- `backend/assets/books/` (primary)
- `backend/books/` (secondary fallback)

How discovery works:

1. On startup, the backend scans both directories for `.pdf`, `.epub`, and
	`.txt` files.
2. A key is derived from each filename stem (slug format).
3. `GET /api/v1/books/examples/dune` resolves key `dune` through this catalog,
	registers it through the same upload-once service path as user uploads, and
	returns a `book_id`.

If an example is missing, the endpoint returns `404` with a structured JSON
message and the backend logs the missing lookup details.

To add a new bundled example:

1. Copy the file into `backend/assets/books/`.
2. Rebuild/redeploy the backend image.
3. Call the corresponding example endpoint.

Startup logs now include:

- bundled example directories scanned
- each discovered example key
- resolved absolute path
- existence status

The backend now performs startup validation and fails fast when any required dependency is unavailable:

- `GEMINI_API_KEY` must be present.
- Gemini SDK must import successfully via `from google import genai`.
- OpenAI SDK must import successfully via `from openai import OpenAI`.

If validation fails, `uvicorn` exits with a clear error message.

## Troubleshooting `google-genai` imports

If you see `cannot import name 'genai' from 'google'`:

1. Activate the same virtual environment used to run the backend.
2. Reinstall dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

3. Verify the SDK import directly:

```bash
python -c "from google import genai; print('Gemini SDK working')"
```

4. Check for conflicting legacy packages and remove them from the environment if needed:

```bash
pip uninstall -y google-generativeai
pip install -U google-genai
```

5. Restart the backend process after package changes.

Set the frontend build environment variable to the public backend origin, then rebuild/redeploy the website:

```dotenv
VITE_MAGIFAB_BACKEND_URL=https://your-movie-api.example
```

## API used by the website

- `POST /api/v1/movies/upload`
- `POST /api/v1/movies/{movie_id}/preprocess`
- `GET /api/v1/movies/{movie_id}/processing-status`
- `GET /api/v1/movies/{movie_id}/scene?timestamp=…`
- `GET /api/v1/movies/{movie_id}/video`
- `POST /api/v1/movies/{movie_id}/companion/chat`
- `POST /api/v1/books/upload`
- `POST /api/v1/books/{book_id}/preprocess`
- `GET /api/v1/books/{book_id}/processing-status`
- `GET /api/v1/books/examples/dune`
- `GET /api/v1/books/{book_id}/chapter?chapter=…`
- `POST /api/v1/books/{book_id}/companion/chat`

Playback only reads stored scenes; it never triggers Gemini or OpenAI.

## Deployment

The Docker image installs FFmpeg and starts this exact command:

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Docker packaging for examples:

- `backend/Dockerfile` explicitly copies `assets/books/` into the image.
- `COPY . ./` keeps fallback `backend/books/` support.

Attach persistent storage for `/app/cache` before production use. The local SQLite and source-video files are stored there; a multi-instance deployment should replace them with the existing Postgres/object-storage repository contracts.
