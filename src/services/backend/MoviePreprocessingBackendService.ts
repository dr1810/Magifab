/** Browser contract for the stored-artifact movie API. No chunk or provider API is exposed here. */
export type ProcessingStatus = 'queued' | 'chunking' | 'analyzing' | 'reasoning' | 'complete' | 'failed'
export type CompanionProfilePayload = { personality: string; accessibility_needs: string[]; difficulties: string[]; preferred_explanation_style: string }
export type ProcessingState = { status: ProcessingStatus; progress: string; percentage: number; error: string | null; title?: string | null }
export type MovieArtifact = {
  timestamp: number
  promptBubble: Array<{ label: string; question: string; answer: string }>
  companionExplanation: string
  visualDrawer: { characters: Array<{ name: string; description: string; emotion: string }>; timeline: string[]; objects: Array<{ name: string; why: string }>; memory: string[]; emotion: string[]; cause: Array<{ cause: string; effect: string }> }
  visualAid: { type: string; description: string }
  characters: Array<{ name: string; description: string; confidence: 'high' | 'medium' | 'low'; source: string }>
  memoryCue: string[]
}

const base = import.meta.env.VITE_MAGIFAB_BACKEND_URL?.trim().replace(/\/$/, '') ?? ''
const endpoint = `${base}/api/v1/movies`

async function json<T>(request: Promise<Response>): Promise<T> {
  const response = await request; const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new Error(body && typeof body === 'object' && 'detail' in body ? String(body.detail) : 'Movie service is unavailable.')
  return body as T
}

export class MoviePreprocessingBackendService {
  private readonly cache = new Map<string, MovieArtifact>()
  async upload(video: File, title?: string) {
    const form = new FormData(); form.append('video', video); if (title) form.append('title', title)
    return json<{ movie_id: string; status: string; reused_existing: boolean }>(fetch(`${endpoint}/upload`, { method: 'POST', body: form }))
  }
  async start(movieId: string, companion_profile: CompanionProfilePayload) {
    return json(fetch(`${endpoint}/${encodeURIComponent(movieId)}/preprocess`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ companion_profile }) }))
  }
  async processMovie(video: File, companion_profile: CompanionProfilePayload, title?: string) { const uploaded = await this.upload(video, title); await this.start(uploaded.movie_id, companion_profile); return uploaded }
  status(movieId: string, signal?: AbortSignal) { return json<ProcessingState>(fetch(`${endpoint}/${encodeURIComponent(movieId)}/processing-status`, { signal })) }
  async getScene(movieId: string, timestamp: number, signal?: AbortSignal) {
    const key = `${movieId}:${Math.floor(timestamp / 90)}`; const cached = this.cache.get(key); if (cached) return cached
    const artifact = await json<MovieArtifact>(fetch(`${endpoint}/${encodeURIComponent(movieId)}/scene?timestamp=${encodeURIComponent(String(Math.max(0, timestamp)))}`, { signal }))
    this.cache.set(`${movieId}:${Math.floor(artifact.timestamp / 90)}`, artifact); return artifact
  }
  chat(movieId: string, timestamp: number, question: string, companion_profile: CompanionProfilePayload) {
    return json<{ answer: string; timestamp: number }>(fetch(`${endpoint}/${encodeURIComponent(movieId)}/companion/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ timestamp, question, companion_profile }) }))
  }
  videoUrl(movieId: string) { return `${endpoint}/${encodeURIComponent(movieId)}/video` }
}
export const moviePreprocessingBackendService = new MoviePreprocessingBackendService()
