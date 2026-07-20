import { answerPrompt } from './StoryResolver'
import type { SceneState } from '../scene/SceneState'
import type { AIProfile, CompanionProfile } from '../../types/user'

export function createCompanionGreeting(state: SceneState | null, companion: CompanionProfile | null) {
  const name = companion?.name || 'Lumi'
  if (!state?.companionEnabled) return `Hi, I’m ${name}. I’m ready when the story begins. What would you like help with?`
  return `Hi, I’m ${name}. Right now, ${state.sceneSummary} What would you like to explore?`
}

export function answerCompanionQuestion(state: SceneState | null, question: string, profile: AIProfile | null) {
  if (!state?.companionEnabled) return 'I can help as soon as the next story moment begins.'
  const answer = answerPrompt(state, question)
  if (profile?.detailLevel === 'Just the essentials') return answer
  if (profile?.detailLevel === 'Give me the full picture') {
    const context = state.memory[0]?.summary || state.relationships[0]?.summary || state.causeEffect[0] ? `${state.causeEffect[0]?.cause ?? state.relationships[0]?.summary ?? state.memory[0]?.summary}` : ''
    return context && context !== answer ? `${answer} Context: ${context}` : answer
  }
  return answer
}
