import type { PromptQuestion } from '../../types/movie'
import type { CompanionProfile, SemanticScene } from './types'

/** Selects brief, profile-aware questions that can be shown as companion prompts. */
export class PromptBuilder {
  /** Builds optional prompts from predicted confusion points without replacing curated prompts. */
  public build(scene: SemanticScene, profile: CompanionProfile): PromptQuestion[] {
    if (profile.interactionFrequency === 'Only when I ask') return []
    return scene.confusionPoints.slice(0, 2).map((point, index) => ({
      id: `ai-${scene.sceneId}-${index}`,
      label: 'Magifab note',
      question: point.suggestedQuestion,
      explanation: point.reason,
    }))
  }
}

export const promptBuilder = new PromptBuilder()
