import { supabase } from '../../lib/supabaseClient'
import { getAccessibilityProfile } from '../accessibilityProfileService'
import type { SceneData } from '../../types/movie'

export type SceneExplanation = {
  explanation: string
  emotion: string
  character: string
}

type ExplainSceneRequest = {
  question: string
  scene: string
  companion: {
    personality: string
    conversationStyle: string
    detailLevel: string
  }
}

function isSceneExplanation(value: unknown): value is SceneExplanation {
  if (!value || typeof value !== 'object') return false
  const response = value as Record<string, unknown>
  return [response.explanation, response.emotion, response.character]
    .every((item) => typeof item === 'string' && item.trim().length > 0)
}

function buildSceneContext(scene: SceneData): string {
  const characters = scene.characterList
    .map((character) => `${character.name} (${character.role}; feeling ${character.emotionalState})`)
    .join(', ')

  return [
    `Scene: ${scene.subtitle}`,
    characters ? `Known characters: ${characters}.` : '',
    scene.emotion ? `Scene emotion: ${scene.emotion}.` : '',
  ].filter(Boolean).join(' ')
}

export class CompanionAIService {
  async explainCharacter(scene: SceneData, question: string): Promise<SceneExplanation> {
    if (!supabase) throw new Error('Supabase is not configured.')

    const profile = await getAccessibilityProfile()
    const request: ExplainSceneRequest = {
      question,
      scene: buildSceneContext(scene),
      companion: {
        personality: profile?.companionProfile.personality ?? 'Warm and encouraging',
        conversationStyle: profile?.companionProfile.conversationStyle ?? 'Simple and direct',
        detailLevel: profile?.aiProfile.detailLevel ?? 'Just the essentials',
      },
    }

    const { data, error } = await supabase.functions.invoke('explain-scene', { body: request })
    if (error) throw error
    if (!isSceneExplanation(data)) throw new Error('The AI service returned an invalid explanation.')
    return {
      explanation: data.explanation.trim(),
      emotion: data.emotion.trim(),
      character: data.character.trim(),
    }
  }
}

export const companionAIService = new CompanionAIService()
