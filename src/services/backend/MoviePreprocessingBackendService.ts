/** Server API client for permanent movie scenes. This browser code never calls AI providers. */
export type MovieProcessingStatus = 'uploaded' | 'processing' | 'completed' | 'partial' | 'failed'
export type SceneConfidence = 'high' | 'medium' | 'low'

export type ProcessedMovie = {
  id: string
  content_hash: string
  title: string | null
  original_filename: string
  mime_type: string
  status: MovieProcessingStatus
  error_message: string | null
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
  gemini_visual_json?: Record<string, unknown> | null
  error_message: string | null
}

export type CanonicalEntity = { name: string; description: string; confidence: SceneConfidence; source: string }
export type CanonicalRelationship = { subject: string; relationship: string; object: string; confidence: SceneConfidence }
export type CanonicalTimelineEvent = { start_seconds: number; end_seconds: number; event: string }
export type CanonicalCauseEffect = { cause: string; effect: string }
export type SearchContext = { entity: string; entity_kind: string; query: string; confidence: number; results: Array<{ title: string; snippet: string; url: string; confidence: number }> }

export type CanonicalSceneDocument = {
  scene_summary: string
  characters: CanonicalEntity[]
  relationships: CanonicalRelationship[]
  objects: CanonicalEntity[]
  locations: string[]
  events: string[]
  timeline: CanonicalTimelineEvent[]
  emotions: string[]
  cause_effect: CanonicalCauseEffect[]
  important_memory: string[]
  difficulty_points: string[]
  visual_aid: { type: string; description: string }
  accessibility_explanation: string
  search_context: SearchContext[]
  confidence: SceneConfidence
}

export type CanonicalMagiFabScene = {
  id: string
  movie_id: string
  chunk_id: string
  canonical_scene: CanonicalSceneDocument
  created_at: string
  updated_at: string
}

export type SceneLookup = { scene: CanonicalMagiFabScene | null; chunk: ProcessedChunk | null }
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
  private readonly movieCache = new Map<string, ProcessedMovie>()
  private readonly timelineCache = new Map<string, ProcessedChunk[]>()
  private readonly sceneCache = new Map<string, SceneLookup>()
  private readonly inFlightScenes = new Map<string, Promise<SceneLookup>>()

  async processMovie(video: File, title?: string) {
    const uploaded = await this.upload(video, title)
    const preprocessing = await this.start(uploaded.movie_id)
    return { ...uploaded, preprocessing }
  }

  async upload(video: File, title?: string): Promise<{ movie_id: string; content_hash: string; status: MovieProcessingStatus; reused_existing: boolean }> {
    const form = new FormData()
    form.append('video', video)
    if (title?.trim()) form.append('title', title.trim())
    return readJson(fetch(`${moviesEndpoint}/upload`, { method: 'POST', body: form }))
  }

  async start(movieId: string): Promise<{ movie_id: string; status: MovieProcessingStatus; accepted: boolean }> {
    this.clear(movieId)
    return readJson(fetch(`${moviesEndpoint}/${encodeURIComponent(movieId)}/preprocess`, { method: 'POST' }))
  }

  async status(movieId: string, signal?: AbortSignal): Promise<MoviePreprocessingStatus> {
    const result = await readJson<MoviePreprocessingStatus>(fetch(`${moviesEndpoint}/${encodeURIComponent(movieId)}/processing-status`, { signal }))
    this.movieCache.set(movieId, result.movie)
    if (result.movie.status === 'completed' || result.movie.status === 'partial') {
      this.timelineCache.delete(movieId)
      for (const key of this.sceneCache.keys()) if (key.startsWith(`${movieId}:`)) this.sceneCache.delete(key)
    }
    return result
  }

  async getMovie(movieId: string, signal?: AbortSignal): Promise<ProcessedMovie> {
    const cached = this.movieCache.get(movieId)
    if (cached) return cached
    const movie = await readJson<ProcessedMovie>(fetch(`${moviesEndpoint}/${encodeURIComponent(movieId)}`, { signal }))
    this.movieCache.set(movieId, movie)
    return movie
  }

  async getTimeline(movieId: string, signal?: AbortSignal): Promise<ProcessedChunk[]> {
    const cached = this.timelineCache.get(movieId)
    if (cached) return cached
    const timeline = await readJson<ProcessedChunk[]>(fetch(`${moviesEndpoint}/${encodeURIComponent(movieId)}/chunks`, { signal }))
    this.timelineCache.set(movieId, timeline)
    return timeline
  }

  async getScene(movieId: string, timestamp: number, signal?: AbortSignal): Promise<SceneLookup> {
    const timeline = await this.getTimeline(movieId, signal)
    const matchingChunk = timeline.find((chunk) => chunk.start_seconds <= timestamp && timestamp < chunk.end_seconds) ?? (timestamp >= (timeline.at(-1)?.end_seconds ?? Infinity) ? timeline.at(-1) : undefined)
    const cacheKey = matchingChunk ? `${movieId}:${matchingChunk.id}` : `${movieId}:at:${Math.floor(timestamp)}`
    const cached = this.sceneCache.get(cacheKey)
    if (cached) return cached
    const pending = this.inFlightScenes.get(cacheKey)
    if (pending) return pending
    const request = readJson<SceneLookup>(fetch(`${moviesEndpoint}/${encodeURIComponent(movieId)}/scene?timestamp=${encodeURIComponent(String(Math.max(0, timestamp)))}`, { signal }))
      .then((result) => {
        const key = result.chunk ? `${movieId}:${result.chunk.id}` : cacheKey
        this.sceneCache.set(key, result)
        return result
      })
      .finally(() => this.inFlightScenes.delete(cacheKey))
    this.inFlightScenes.set(cacheKey, request)
    return request
  }

  async preloadNearbyScenes(movieId: string, timestamp: number): Promise<void> {
    const timeline = await this.getTimeline(movieId)
    const index = timeline.findIndex((chunk) => chunk.start_seconds <= timestamp && timestamp < chunk.end_seconds)
    await Promise.all([timeline[index - 1], timeline[index + 1]].filter((chunk): chunk is ProcessedChunk => Boolean(chunk)).map((chunk) => this.getScene(movieId, chunk.start_seconds)))
  }

  async getVisualAid(movieId: string, timestamp: number): Promise<CanonicalSceneDocument['visual_aid'] | null> {
    return (await this.getScene(movieId, timestamp)).scene?.canonical_scene.visual_aid ?? null
  }

  videoUrl(movieId: string) { return `${moviesEndpoint}/${encodeURIComponent(movieId)}/video` }

  clear(movieId: string) {
    this.movieCache.delete(movieId)
    this.timelineCache.delete(movieId)
    for (const key of this.sceneCache.keys()) if (key.startsWith(`${movieId}:`)) this.sceneCache.delete(key)
  }
}

export const moviePreprocessingBackendService = new MoviePreprocessingBackendService()
