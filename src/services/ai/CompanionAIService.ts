import { supabase } from '../../lib/supabaseClient'
import { getAccessibilityProfile } from '../accessibilityProfileService'

export type SceneExplanation = {
  explanation: string
  emotion: string
  character: string | null
  characterFound: boolean
  confidence: number
  anchor: { x: number; y: number; width: number; height: number }
  visualAidType: 'magnifier' | 'highlight'
}

type PersonalizeRequest = {
  mode: 'personalize'
  question: string
  semanticContext: Record<string, unknown>
  companion: {
    personality: string
    conversationStyle: string
    detailLevel: string
  }
}

export type PersonalizedExplanation = Pick<SceneExplanation, 'explanation' | 'emotion'>

function isPersonalizedExplanation(value: unknown): value is PersonalizedExplanation {
  if (!value || typeof value !== 'object') return false
  const response = value as Record<string, unknown>
  return typeof response.explanation === 'string' && response.explanation.trim().length > 0
    && typeof response.emotion === 'string' && response.emotion.trim().length > 0
}

export class CompanionAIService {
  /** GPT receives only verified semantic facts and turns them into accessible language. */
  async personalizeExplanation(question: string, semanticContext: Record<string, unknown>): Promise<PersonalizedExplanation> {
    if (!supabase) throw new Error('Supabase is not configured.')

    const profile = await getAccessibilityProfile()
    const request: PersonalizeRequest = {
      mode: 'personalize',
      question,
      semanticContext,
      companion: {
        personality: profile?.companionProfile.personality ?? 'Warm and encouraging',
        conversationStyle: profile?.companionProfile.conversationStyle ?? 'Simple and direct',
        detailLevel: profile?.aiProfile.detailLevel ?? 'Just the essentials',
      },
    }

    const { data, error } = await supabase.functions.invoke('explain-scene', { body: request })
    if (error) throw error
    if (!isPersonalizedExplanation(data)) throw new Error('The AI service returned an invalid explanation.')
    return {
      explanation: data.explanation.trim(),
      emotion: data.emotion.trim(),
    }
  }
}

export const companionAIService = new CompanionAIService()
