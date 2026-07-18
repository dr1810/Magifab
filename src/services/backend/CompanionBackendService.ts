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
export type BackendTimelineSummary = { summary: string; confidence: number }
export type BackendEmotionSummary = { emotion_id: string; summary: string; confidence: number }
export type BackendMemoryReminder = { summary: string; confidence: number }
export type BackendVocabularyAssistance = { term: string; simple_definition: string; confidence: number }
export type BackendConversationSimplification = { dialogue_id: string; simple_text: string; confidence: number }

export type BackendAccessibilityContent = {
  companion_tone: string
  scene_summary: string
  likely_confusions: Array<{ kind: string; confidence: number; reason: string }>
  prompt_bubbles: Array<{ id: string; kind: string; label: string; question: string; priority: number }>
  drawer: {
    character_cards: BackendCharacterCard[]
    relationship_summaries: BackendRelationshipSummary[]
    timeline_summary: BackendTimelineSummary | null
    emotion_summaries: BackendEmotionSummary[]
    memory_reminders: BackendMemoryReminder[]
    vocabulary_assistance: BackendVocabularyAssistance[]
    conversation_simplifications: BackendConversationSimplification[]
  }
}

export type CompanionBackendResponse = {
  knowledge_source: 'retrieved' | 'expanded'
  response_cache_hit: boolean
  cache_key: string
  knowledge_revision: number
  response: { response: string; model: string }
  accessibility_content: BackendAccessibilityContent
  perception?: unknown
  semantic_matches?: {
    character_found: boolean
    characters: Array<{ id: string; label: string; confidence: number; entity?: { bounding_box?: number[] | null } }>
  } | null
}

type PreparedPromptBubble = {
  id: string
  type: string
  title: string
  question: string
  target_entity?: string | null
  bounding_box?: number[] | null
  priority: number
  cached: boolean
}

type ScenePreparationBackendResponse = Omit<CompanionBackendResponse, 'response_cache_hit' | 'cache_key' | 'response'> & {
  prompt_bubbles?: PreparedPromptBubble[]
}

type BackendRequest = {
  movie_id: string
  timestamp_seconds: number
  scene_id: string
  scene_summary: string
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

/** Matches FastAPI's ScenePreparationRequest exactly; preparation does not need prompt intent. */
type ScenePreparationRequest = Pick<
  BackendRequest,
  'movie_id' | 'timestamp_seconds' | 'scene_id' | 'scene_summary' | 'image' | 'accessibility_profile' | 'companion_profile'
> & { image: string }

type RespondOptions = {
  movieId: string
  scene: SceneData
  question: string
  timestamp: number
  settings: Settings
  companion: CompanionProfile | null
  signal?: AbortSignal
}

type PrepareOptions = Omit<RespondOptions, 'question' | 'timestamp'> & { frame: CapturedVideoFrame }

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
  const personalized = response.response as Record<string, unknown> | undefined
  const content = response.accessibility_content as Record<string, unknown> | undefined
  return typeof response.knowledge_source === 'string'
    && typeof response.response_cache_hit === 'boolean'
    && typeof personalized?.response === 'string'
    && typeof content?.scene_summary === 'string'
    && typeof content?.drawer === 'object'
}

export class CompanionBackendService {
  /** The React app only sends frame/context/profile data; all accessibility reasoning remains server-side. */
  async respond(options: RespondOptions): Promise<CompanionBackendResponse> {
    const savedProfile = await getAccessibilityProfile()
    const intent = promptIntent(options.question)
    const payload: BackendRequest = {
      movie_id: options.movieId,
      timestamp_seconds: options.timestamp,
      scene_id: options.scene.sceneId,
      scene_summary: options.scene.subtitle || options.scene.voiceNarration || 'Current movie scene.',
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

  async prepareScene(options: PrepareOptions): Promise<CompanionBackendResponse> {
    const savedProfile = await getAccessibilityProfile()
    const payload: ScenePreparationRequest = {
      movie_id: options.movieId, timestamp_seconds: options.frame.timestamp, scene_id: options.scene.sceneId,
      scene_summary: options.scene.subtitle || options.scene.voiceNarration || 'Current movie scene.',
      image: options.frame.dataUrl, ...profilePayload(options.settings, options.companion, savedProfile),
    }
    const payloadJson = JSON.stringify(payload)
    if (import.meta.env.DEV) console.debug('[MagiFab companion] prepare payload', payloadJson)
    const response = await fetch(companionEndpoint.replace('/respond', '/prepare'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payloadJson, signal: options.signal,
    })
    const body: unknown = await response.json().catch(() => null)
    if (!response.ok) {
      const detail = body && typeof body === 'object' && 'detail' in body ? String(body.detail) : 'The scene preparation service is unavailable.'
      throw new Error(detail)
    }
    if (!body || typeof body !== 'object' || !('accessibility_content' in body) || !('knowledge_revision' in body)) {
      throw new Error('The scene preparation service returned an invalid response.')
    }
    const prepared = body as ScenePreparationBackendResponse
    const preparedBubbles = Array.isArray(prepared.prompt_bubbles) ? prepared.prompt_bubbles : null
    // The prompt panel consumes the first-class preparation map. Retain the
    // nested content shape only as the compatibility contract for the drawer.
    const accessibilityContent: BackendAccessibilityContent = preparedBubbles
      ? {
          ...prepared.accessibility_content,
          prompt_bubbles: preparedBubbles.map((bubble) => ({
            id: bubble.id,
            kind: bubble.type,
            label: bubble.title,
            question: bubble.question,
            priority: bubble.priority,
          })),
        }
      : prepared.accessibility_content
    return {
      ...prepared,
      accessibility_content: accessibilityContent,
      response_cache_hit: false,
      cache_key: '',
      response: { response: '', model: 'scene-preparation' },
    }
  }
}

export const companionBackendService = new CompanionBackendService()
