import { getAccessibilityProfile } from '../accessibilityProfileService'
import type { CapturedVideoFrame } from '../ai/VideoFrameCaptureService'
import type { Settings } from '../../types/accessibility'
import type { CompanionProfile } from '../../types/user'
import type { SceneData } from '../../types/movie'

export type BackendCharacterCard = {
  character_id: string
  name: string
  reminder: string
  confidence: number
  visual_anchor?: { bbox: number[]; confidence: number } | null
}

export type BackendRelationshipSummary = { relationship_id: string; summary: string; confidence: number }
export type BackendEmotionSummary = { emotion_id: string; summary: string; confidence: number }
export type BackendMemoryReminder = { summary: string; confidence: number }
export type BackendVocabularyAssistance = { term: string; simple_definition: string; confidence: number }
export type BackendConversationSimplification = { dialogue_id: string; simple_text: string; confidence: number }

export type IntervalState = {
  metadata: { interval_id: string; catalog_scene_id: string | null; movie_id: string; start_time: number; end_time: number | null; interval_number: number; knowledge_revision: number }
  prompts: {
    prompt_bubbles: Array<{ id: string; kind: string; label: string; question: string; priority: number; claim_ids?: string[]; timestamp_start?: number; timestamp_end?: number; semantic_event?: string; screen_location?: string }>
    prompt_answers: Array<{ prompt_id: string; question: string; answer: string }>
    suggested_questions: string[]
  }
  visualDrawer: { story_now: string[]; relationships: string[]; timeline: string[]; emotion: string | null; cause_effect: Array<{ cause: string; effect: string }>; objects: string[]; memory: string[] }
  storyState: { scene_summary: string | null; current_goal: string; current_interval_id: string | null; timeline_position: string | null; story_so_far: string[]; unresolved_threads: string[] }
  characters: BackendCharacterCard[]
  relationships: BackendRelationshipSummary[]
  memory: BackendMemoryReminder[]
  conversationContext: { scene_explanation: string; simplifications: BackendConversationSimplification[] }
  accessibilityHints: { vocabulary: BackendVocabularyAssistance[]; emotions: BackendEmotionSummary[] }
  semanticMemoryBefore: { active_characters: string[]; relationships: string[]; emotions: string[]; important_objects: string[]; unresolved_threads: string[]; story_events: string[] }
  semanticMemoryAfter: { active_characters: string[]; relationships: string[]; emotions: string[]; important_objects: string[]; unresolved_threads: string[]; story_events: string[] }
  cacheMetadata: { semantic_cache_key: string; knowledge_source: string; semantic_map_cached: boolean; frame_hash: string | null }
}

export type CompanionBackendResponse = IntervalState
export type IntervalPreparationResponse = IntervalState

type BackendRequest = {
  movie_id: string
  timestamp_seconds: number
  question: string
  intent: string
  image?: string
  grounding_queries: string[]
  verify_faces: boolean
  accessibility_profile: {
    accessibility_needs: string[]
    detail_level: string
    preferred_prompt_types: string[]
    conversation_simplification: boolean
    vocabulary_assistance: boolean
  }
  companion_profile: { name: string; personality: string; conversation_style: string }
}

/** Matches FastAPI's interval-preprocessing request; it never includes prompt intent. */
type IntervalPreparationRequest = Pick<
  BackendRequest,
  'movie_id' | 'timestamp_seconds' | 'image' | 'accessibility_profile' | 'companion_profile'
> & {
  image: string
  interval_id: string
  interval_number: number
  interval_start: number
  interval_end: number
  catalog_scene_id: string | null
}

type RespondOptions = {
  movieId: string
  scene: SceneData | null
  question: string
  timestamp: number
  settings: Settings
  companion: CompanionProfile | null
  signal?: AbortSignal
}

type PrepareOptions = Omit<RespondOptions, 'question' | 'timestamp' | 'signal'> & {
  frame: CapturedVideoFrame
  intervalNumber: number
  intervalStart: number
  intervalEnd: number
  catalogScene: SceneData | null
}

const configuredBackendUrl = import.meta.env.VITE_MAGIFAB_BACKEND_URL?.trim()
/**
 * Development requests go through Vite's same-origin `/api` proxy. This avoids
 * treating the browser's loopback interface as the backend host. Deployments
 * provide their public backend origin through `VITE_MAGIFAB_BACKEND_URL`.
 */
const companionEndpoint = configuredBackendUrl
  ? `${configuredBackendUrl.replace(/\/$/, '')}/api/v1/companion/respond`
  : '/api/v1/companion/respond'

function promptIntent(question: string): string {
  const value = question.toLowerCase()
  if (/\bwho\b/.test(value)) return 'character_identity'
  if (/relationship|connected/.test(value)) return 'relationship'
  if (/feel|emotion|sad|angry/.test(value)) return 'emotion'
  if (/happen|plot|before/.test(value)) return 'timeline'
  if (/object|holding|where|what is this/.test(value)) return 'object_location'
  return 'scene_explanation'
}

function profilePayload(settings: Settings, companion: CompanionProfile | null, saved: Awaited<ReturnType<typeof getAccessibilityProfile>>): Pick<BackendRequest, 'accessibility_profile' | 'companion_profile'> {
  const ai = saved?.aiProfile
  const needs = ai?.difficultyAreas ?? []
  return {
    accessibility_profile: {
      accessibility_needs: needs,
      detail_level: ai?.detailLevel ?? 'brief',
      preferred_prompt_types: ai?.preferredPromptTypes ?? [],
      conversation_simplification: !settings.reduceDistractions,
      vocabulary_assistance: true,
    },
    companion_profile: {
      name: companion?.name ?? saved?.companionProfile.name ?? 'Lumi',
      personality: companion?.personality ?? saved?.companionProfile.personality ?? 'warm',
      conversation_style: companion?.conversationStyle ?? saved?.companionProfile.conversationStyle ?? 'simple',
    },
  }
}

function isBackendResponse(value: unknown): value is CompanionBackendResponse {
  if (!value || typeof value !== 'object') return false
  const response = value as Record<string, unknown>
  const metadata = response.metadata as Record<string, unknown> | undefined
  const prompts = response.prompts as Record<string, unknown> | undefined
  return typeof metadata?.interval_id === 'string' && Array.isArray(prompts?.prompt_bubbles)
}

export class CompanionBackendService {
  private readonly activePreparationRequests = new Map<string, Promise<IntervalPreparationResponse>>()

  /** Prompt clicks request an answer only; they never create a new interval state. */
  async respond(options: RespondOptions): Promise<CompanionBackendResponse> {
    const savedProfile = await getAccessibilityProfile()
    const intent = promptIntent(options.question)
    const payload: BackendRequest = {
      movie_id: options.movieId,
      timestamp_seconds: options.timestamp,
      question: options.question,
      intent,
      grounding_queries: [],
      verify_faces: false,
      ...profilePayload(options.settings, options.companion, savedProfile),
    }
    const response = await fetch(companionEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: options.signal,
    })
    const body: unknown = await response.json().catch(() => null)
    if (!response.ok) {
      const detail = body && typeof body === 'object' && 'detail' in body ? String(body.detail) : 'The companion backend is unavailable.'
      throw new Error(detail)
    }
    if (!isBackendResponse(body)) throw new Error('The companion backend returned an invalid response.')
    return body
  }

  /** Called once per chronological fixed 10-second interval before playback begins. */
  async prepareInterval(options: PrepareOptions): Promise<IntervalPreparationResponse> {
    const savedProfile = await getAccessibilityProfile()
    const payload: IntervalPreparationRequest = {
      movie_id: options.movieId,
      timestamp_seconds: options.frame.timestamp,
      interval_id: `${options.movieId}:interval:${options.intervalNumber}`,
      interval_number: options.intervalNumber,
      interval_start: options.intervalStart,
      interval_end: options.intervalEnd,
      catalog_scene_id: options.catalogScene?.sceneId ?? null,
      image: options.frame.dataUrl, ...profilePayload(options.settings, options.companion, savedProfile),
    }
    const requestKey = JSON.stringify({
      movie_id: payload.movie_id,
      interval_id: payload.interval_id,
      accessibility_profile: payload.accessibility_profile,
    })
    const activeRequest = this.activePreparationRequests.get(requestKey)
    if (activeRequest) return activeRequest

    const request = this.sendPreparationRequest(payload)
    this.activePreparationRequests.set(requestKey, request)
    void request.finally(() => {
      if (this.activePreparationRequests.get(requestKey) === request) this.activePreparationRequests.delete(requestKey)
    }).catch(() => undefined)
    return request
  }

  async completeMoviePreprocessing(movieId: string, expectedIntervals: number): Promise<void> {
    const response = await fetch(companionEndpoint.replace('/respond', '/preprocessing/complete'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie_id: movieId, expected_intervals: expectedIntervals }),
    })
    if (!response.ok) throw new Error('Interval preprocessing validation failed.')
  }

  private async sendPreparationRequest(payload: IntervalPreparationRequest): Promise<IntervalPreparationResponse> {
    const payloadJson = JSON.stringify(payload)
    if (import.meta.env.DEV) console.debug('[MagiFab companion] prepare payload', payloadJson)
    const response = await fetch(companionEndpoint.replace('/respond', '/prepare'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payloadJson,
    })
    const body: unknown = await response.json().catch(() => null)
    if (!response.ok) {
      const detail = body && typeof body === 'object' && 'detail' in body ? String(body.detail) : 'The scene preparation service is unavailable.'
      throw new Error(detail)
    }
    if (!isBackendResponse(body)) {
      throw new Error('The scene preparation service returned an invalid response.')
    }
    return body as IntervalPreparationResponse
  }
}

export const companionBackendService = new CompanionBackendService()
