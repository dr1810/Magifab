/** Browser contract for the stored-artifact movie API. No chunk or provider API is exposed here. */
import { buildBackendUrl, requestBackendJson } from './apiClient'

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

export class MoviePreprocessingBackendService {
  private readonly cache = new Map<string, MovieArtifact>()
  async upload(video: File, title?: string) {
    const form = new FormData(); form.append('video', video); if (title) form.append('title', title)
    return requestBackendJson<{ movie_id: string; status: string; reused_existing: boolean }>('/api/v1/movies/upload', { method: 'POST', body: form, timeoutMs: 60_000 })
  }
  async start(movieId: string, companion_profile: CompanionProfilePayload) {
    return requestBackendJson<{ movie_id: string; status: string; accepted: boolean }>(`/api/v1/movies/${encodeURIComponent(movieId)}/preprocess`, { method: 'POST', jsonBody: { companion_profile }, timeoutMs: 45_000 })
  }
  async processMovie(video: File, companion_profile: CompanionProfilePayload, title?: string) { const uploaded = await this.upload(video, title); await this.start(uploaded.movie_id, companion_profile); return uploaded }
  status(movieId: string, signal?: AbortSignal) { return requestBackendJson<ProcessingState>(`/api/v1/movies/${encodeURIComponent(movieId)}/processing-status`, { signal }) }
  async getScene(movieId: string, timestamp: number, signal?: AbortSignal) {
    const key = `${movieId}:${Math.floor(timestamp / 90)}`; const cached = this.cache.get(key); if (cached) return cached
    const artifact = await requestBackendJson<MovieArtifact>(`/api/v1/movies/${encodeURIComponent(movieId)}/scene`, { query: { timestamp: Math.max(0, timestamp) }, signal })
    this.cache.set(`${movieId}:${Math.floor(artifact.timestamp / 90)}`, artifact); return artifact
  }
  chat(movieId: string, timestamp: number, question: string, companion_profile: CompanionProfilePayload) {
    return requestBackendJson<{ answer: string; timestamp: number }>(`/api/v1/movies/${encodeURIComponent(movieId)}/companion/chat`, { method: 'POST', jsonBody: { timestamp, question, companion_profile }, timeoutMs: 45_000 })
  }
  videoUrl(movieId: string) { return buildBackendUrl(`/api/v1/movies/${encodeURIComponent(movieId)}/video`) }
}
export const moviePreprocessingBackendService = new MoviePreprocessingBackendService()
