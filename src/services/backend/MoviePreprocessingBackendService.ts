/** Server API client for permanent movie scenes. This browser code never calls AI providers. */
export type MovieProcessingStatus = 'uploaded' | 'processing' | 'completed' | 'partial' | 'failed'

export type ProcessedMovie = {
  id: string
  content_hash: string
  title: string | null
  original_filename: string
  mime_type: string
  status: MovieProcessingStatus
  created_at: string
  updated_at: string
}

export type ProcessedChunk = {
  id: string
  movie_id: string
  sequence_number: number
  start_seconds: number
  end_seconds: number
  duration_seconds: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  gemini_visual_json: Record<string, unknown> | null
  error_message: string | null
}

export type CanonicalMagiFabScene = {
  id: string
  movie_id: string
  chunk_id: string
  canonical_scene: {
    scene_summary: string
    characters: Array<Record<string, unknown>>
    relationships: Array<Record<string, unknown>>
    objects: Array<Record<string, unknown>>
    locations: string[]
    events: string[]
    timeline: Array<Record<string, unknown>>
    emotions: string[]
    important_memory: string[]
    difficulty_points: string[]
    visual_aid: { type: string; description: string }
    accessibility_explanation: string
    search_context: Array<Record<string, unknown>>
    confidence: 'high' | 'medium' | 'low'
  }
}

export type MoviePreprocessingStatus = { movie: ProcessedMovie; chunk_counts: Record<string, number> }

const backendBaseUrl = import.meta.env.VITE_MAGIFAB_BACKEND_URL?.trim().replace(/\/$/, '') ?? ''
const moviesEndpoint = `${backendBaseUrl}/api/v1/movies`

async function readJson<T>(responsePromise: Promise<Response>): Promise<T> {
  const response = await responsePromise
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? String(body.detail) : 'Movie preprocessing is unavailable.'
    throw new Error(detail)
  }
  return body as T
}

export class MoviePreprocessingBackendService {
  async upload(video: File, title?: string): Promise<{ movie_id: string; content_hash: string; status: MovieProcessingStatus; reused_existing: boolean }> {
    const form = new FormData()
    form.append('video', video)
    if (title?.trim()) form.append('title', title.trim())
    return readJson(fetch(`${moviesEndpoint}/upload`, { method: 'POST', body: form }))
  }

  async start(movieId: string): Promise<{ movie_id: string; status: MovieProcessingStatus; accepted: boolean }> {
    return readJson(fetch(`${moviesEndpoint}/${encodeURIComponent(movieId)}/preprocess`, { method: 'POST' }))
  }

  async status(movieId: string): Promise<MoviePreprocessingStatus> {
    return readJson(fetch(`${moviesEndpoint}/${encodeURIComponent(movieId)}/processing-status`))
  }

  async scenes(movieId: string): Promise<CanonicalMagiFabScene[]> {
    return readJson(fetch(`${moviesEndpoint}/${encodeURIComponent(movieId)}/scenes`))
  }

  async chunks(movieId: string): Promise<ProcessedChunk[]> {
    return readJson(fetch(`${moviesEndpoint}/${encodeURIComponent(movieId)}/chunks`))
  }
}

export const moviePreprocessingBackendService = new MoviePreprocessingBackendService()
