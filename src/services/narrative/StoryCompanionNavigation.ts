import type { SceneState } from '../scene/SceneState'

export type StoryCompanionTab = 'story' | 'characters' | 'relationships' | 'emotions' | 'objects' | 'memory' | 'timeline' | 'causeEffect' | 'conversation' | 'summary'

export type StoryCompanionPromptContext = {
  id: string
  question: string
  answer: string
  tab: StoryCompanionTab
  visualAid: string
}

export function resolveStoryCompanionTab(kind: string, question: string): StoryCompanionTab {
  const normalizedKind = kind.toLowerCase()
  const normalizedQuestion = question.toLowerCase()
  if (/character/.test(normalizedKind) || /who is|who are/.test(normalizedQuestion)) return 'characters'
  if (/^why is .+ (annoyed|frustrated|upset) with /.test(normalizedQuestion)) return 'characters'
  if (/relationship/.test(normalizedKind) || /together|connected|between/.test(normalizedQuestion)) return 'relationships'
  if (/emotion|feeling/.test(normalizedKind) || /feel|angry|upset|annoyed|frustrated|afraid|scared/.test(normalizedQuestion)) return 'emotions'
  if (/memory/.test(normalizedKind) || /earlier|remember|before/.test(normalizedQuestion)) return 'memory'
  if (/object|vocabulary/.test(normalizedKind) || /object|word|mean/.test(normalizedQuestion)) return 'objects'
  if (/conversation/.test(normalizedKind) || /talking|say|conversation/.test(normalizedQuestion)) return 'conversation'
  if (/cause|plot/.test(normalizedKind) || /why did|what caused|how did/.test(normalizedQuestion)) return 'causeEffect'
  if (/timeline/.test(normalizedKind)) return 'timeline'
  return 'story'
}

export function createStoryCompanionPromptContext(
  prompt: { id: string; kind: string; question: string },
  answer: string,
  state: SceneState,
): StoryCompanionPromptContext {
  const tab = resolveStoryCompanionTab(prompt.kind, prompt.question)
  return { id: prompt.id, question: prompt.question, answer, tab, visualAid: visualAidFor(tab, state) }
}

function visualAidFor(tab: StoryCompanionTab, state: SceneState) {
  if (tab === 'characters') return state.characters.map((character) => character.name).join(' · ') || 'Character details are available in this story moment.'
  if (tab === 'relationships') return state.relationships[0]?.summary ?? state.characters.map((character) => character.reminder).join(' · ')
  if (tab === 'emotions') return state.emotions[0]?.summary ?? state.sceneSummary
  if (tab === 'objects') return state.importantObjects.join(' · ') || 'No important object is verified in this moment.'
  if (tab === 'memory') return state.memory[0]?.summary ?? 'No earlier event is needed to understand this moment.'
  if (tab === 'timeline') return state.timeline.join(' → ')
  if (tab === 'causeEffect') {
    const event = state.causeEffect[0]
    return event ? `${event.cause} → ${event.effect}` : state.sceneSummary
  }
  if (tab === 'conversation') return state.conversation.sceneExplanation
  return state.sceneSummary
}
