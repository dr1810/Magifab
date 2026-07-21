# MagiFab Movie API

This is the slim, server-only backend used by the main MagiFab website.

It has one intelligence path only:

```text
movie upload → 90-second chunks → Gemini video → Google Search evidence
→ OpenAI canonical scene → stored scene retrieval during playback
```

It does **not** install or start YOLO, Florence, Grounding DINO, Torch, Hugging Face, or any frame-analysis model.

## Run locally

FFmpeg and ffprobe are required for chunking:

```bash
brew install ffmpeg
cd /Users/rameshlathimuthu/Desktop/Magifab/backend
python3 -m venv .venv-movie
source .venv-movie/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
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

Playback only reads stored scenes; it never triggers Gemini or OpenAI.

## Deployment

The Docker image installs FFmpeg and starts this exact command:

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Attach persistent storage for `/app/cache` before production use. The local SQLite and source-video files are stored there; a multi-instance deployment should replace them with the existing Postgres/object-storage repository contracts.
